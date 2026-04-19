from __future__ import annotations

import os
import queue
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from scraper.app_update import (
    APP_VERSION,
    UpdateInfo,
    apply_update_and_restart,
    check_for_update,
    download_update_binary,
    get_update_config_path,
    is_frozen_app,
)
from scraper.trust_bridge_runner import TrustBridgeRunConfig, run_trust_bridge

STATE_SOURCE_MAP: dict[str, str] = {
    "CA": "ca_humboldt_parcels",
    "OR": "or_deschutes_taxlots",
}


class TrustBridgeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Trust Bridge Lead Builder")
        self.root.geometry("760x590")
        self.root.minsize(720, 560)

        self.events: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.state_ca = tk.BooleanVar(value=True)
        self.state_or = tk.BooleanVar(value=True)
        self.allow_missing_phone = tk.BooleanVar(value=True)
        self.prefer_owner_occupied = tk.BooleanVar(
            value=os.getenv("TRUST_BRIDGE_PREFER_OWNER_OCCUPIED", "1") == "1"
        )
        self.output_format = tk.StringVar(value="csv")
        self.per_source_limit = tk.StringVar(
            value=os.getenv("TRUST_BRIDGE_PER_SOURCE_LIMIT", "500")
        )
        self.final_limit = tk.StringVar(value=os.getenv("TRUST_BRIDGE_FINAL_LIMIT", "200"))
        self.city_filter = tk.StringVar(value="")
        self.output_folder = tk.StringVar(value=str(Path("data").resolve()))
        self.output_name = tk.StringVar(value="trust_bridge_leads")
        self.progress_value = tk.IntVar(value=0)
        self.status_text = tk.StringVar(value="Ready")

        self._build_ui()
        self._poll_events()
        self.root.after(800, self._start_update_check)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="Trust Bridge Lead Builder", font=("Segoe UI", 14, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Label(header, text=f"v{APP_VERSION}", foreground="#555").pack(side=tk.LEFT, padx=10)
        ttk.Button(header, text="Help", command=self._show_help).pack(side=tk.RIGHT)

        states = ttk.LabelFrame(main, text="States")
        states.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(states, text="California (CA)", variable=self.state_ca).pack(
            side=tk.LEFT, padx=8, pady=6
        )
        ttk.Checkbutton(states, text="Oregon (OR)", variable=self.state_or).pack(
            side=tk.LEFT, padx=8, pady=6
        )
        ttk.Label(
            states,
            text="Sources are auto-assigned by state selection.",
        ).pack(side=tk.LEFT, padx=10, pady=6)

        filters = ttk.LabelFrame(main, text="Filters")
        filters.pack(fill=tk.X, pady=(0, 8))
        grid = ttk.Frame(filters)
        grid.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(grid, text="Fetch limit (per state source):").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Entry(grid, textvariable=self.per_source_limit, width=12).grid(
            row=0, column=1, sticky=tk.W, padx=8, pady=2
        )
        ttk.Label(grid, text="Final lead limit:").grid(row=0, column=2, sticky=tk.W, pady=2)
        ttk.Entry(grid, textvariable=self.final_limit, width=12).grid(
            row=0, column=3, sticky=tk.W, padx=8, pady=2
        )

        ttk.Label(grid, text="City filter (optional, exact match):").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        ttk.Entry(grid, textvariable=self.city_filter, width=25).grid(
            row=1, column=1, sticky=tk.W, padx=8, pady=2
        )
        ttk.Label(grid, text="Output format:").grid(row=1, column=2, sticky=tk.W, pady=2)
        fmt = ttk.Combobox(
            grid,
            textvariable=self.output_format,
            values=["csv", "xlsx"],
            width=10,
            state="readonly",
        )
        fmt.grid(row=1, column=3, sticky=tk.W, padx=8, pady=2)

        ttk.Checkbutton(
            grid,
            text="Allow missing phone",
            variable=self.allow_missing_phone,
        ).grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Checkbutton(
            grid,
            text="Prefer owner-occupied",
            variable=self.prefer_owner_occupied,
        ).grid(row=2, column=1, sticky=tk.W, pady=4)

        output = ttk.LabelFrame(main, text="Output")
        output.pack(fill=tk.X, pady=(0, 8))
        out_grid = ttk.Frame(output)
        out_grid.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(out_grid, text="Folder:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(out_grid, textvariable=self.output_folder, width=62).grid(
            row=0, column=1, sticky=tk.W, padx=8, pady=2
        )
        ttk.Button(out_grid, text="Browse", command=self._browse_folder).grid(
            row=0, column=2, padx=4, pady=2
        )

        ttk.Label(out_grid, text="File name:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(out_grid, textvariable=self.output_name, width=32).grid(
            row=1, column=1, sticky=tk.W, padx=8, pady=2
        )

        controls = ttk.Frame(main)
        controls.pack(fill=tk.X, pady=(4, 8))
        self.start_button = ttk.Button(controls, text="Start", command=self._start)
        self.start_button.pack(side=tk.LEFT)
        ttk.Button(controls, text="Exit", command=self.root.destroy).pack(side=tk.LEFT, padx=8)

        progress_frame = ttk.LabelFrame(main, text="Progress")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        self.progress = ttk.Progressbar(
            progress_frame,
            mode="determinate",
            variable=self.progress_value,
            maximum=100,
        )
        self.progress.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(progress_frame, textvariable=self.status_text).pack(
            anchor=tk.W, padx=8, pady=(0, 6)
        )

        self.log = tk.Text(progress_frame, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _show_help(self) -> None:
        update_note = "Auto-update: checks on app startup and prompts if a new version exists."
        if not is_frozen_app():
            update_note = (
                "Auto-update works in the packaged .exe. "
                "When running via Python source, updates are disabled."
            )

        messagebox.showinfo(
            "How It Works",
            (
                "1. Choose state(s). Sources are picked automatically.\n"
                "2. Set fetch limit and final lead limit.\n"
                "3. Optional: set a city exact-match filter.\n"
                "4. Choose output folder, file name, and format.\n"
                "5. Click Start.\n\n"
                "Fetch limit (per state source): records fetched from each state's source before filtering.\n"
                "Final lead limit: max rows after filtering + deduplication.\n"
                "The app fetches records, applies your current Trust Bridge filters,\n"
                "deduplicates results, and exports the file. Progress/status appears live.\n\n"
                f"{update_note}"
            ),
        )

    def _browse_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_folder.get() or str(Path.cwd()))
        if selected:
            self.output_folder.set(selected)

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        try:
            config = self._build_config()
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.progress_value.set(0)
        self.status_text.set("Starting...")
        self._log("Starting run...")
        self.start_button.configure(state=tk.DISABLED)

        self.worker = threading.Thread(target=self._run_worker, args=(config,), daemon=True)
        self.worker.start()

    def _build_config(self) -> TrustBridgeRunConfig:
        states: list[str] = []
        if self.state_ca.get():
            states.append("CA")
        if self.state_or.get():
            states.append("OR")
        if not states:
            raise ValueError("Select at least one state.")

        source_keys = self._resolve_sources(states)

        per_source_limit = int(self.per_source_limit.get().strip())
        final_limit = int(self.final_limit.get().strip())
        if per_source_limit <= 0 or final_limit <= 0:
            raise ValueError("Limits must be positive numbers.")

        folder = Path(self.output_folder.get().strip() or ".")
        file_name = self.output_name.get().strip()
        if not file_name:
            raise ValueError("File name is required.")

        ext = ".xlsx" if self.output_format.get() == "xlsx" else ".csv"
        if file_name.lower().endswith(".csv") or file_name.lower().endswith(".xlsx"):
            output_path = folder / file_name
        else:
            output_path = folder / f"{file_name}{ext}"

        city_text = self.city_filter.get().strip()
        city = city_text if city_text else None

        return TrustBridgeRunConfig(
            source_keys=source_keys,
            states=tuple(states),
            per_source_limit=per_source_limit,
            final_limit=final_limit,
            city=city,
            output_path=output_path,
            allow_missing_phone=self.allow_missing_phone.get(),
            prefer_owner_occupied=self.prefer_owner_occupied.get(),
            enrichment_url=os.getenv("TRUST_BRIDGE_ENRICHMENT_URL", "").strip(),
            enrichment_api_key=os.getenv("TRUST_BRIDGE_ENRICHMENT_API_KEY", "").strip(),
            enrichment_auth_header=os.getenv(
                "TRUST_BRIDGE_ENRICHMENT_AUTH_HEADER", "X-API-Key"
            ).strip(),
            enrichment_delay_seconds=float(
                os.getenv("TRUST_BRIDGE_ENRICHMENT_DELAY_SECONDS", "0.2")
            ),
        )

    def _resolve_sources(self, states: list[str]) -> list[str]:
        keys: list[str] = []
        for state in states:
            source = STATE_SOURCE_MAP.get(state)
            if source and source not in keys:
                keys.append(source)
        if not keys:
            raise ValueError("No source mapping found for selected state(s).")
        return keys

    def _run_worker(self, config: TrustBridgeRunConfig) -> None:
        try:
            result = run_trust_bridge(config, progress=self._emit_progress)
            self.events.put(("done", {"result": result}))
        except Exception as exc:
            self.events.put(
                (
                    "error",
                    {
                        "message": str(exc),
                        "trace": traceback.format_exc(),
                    },
                )
            )

    def _emit_progress(self, percent: int, status: str) -> None:
        self.events.put(("progress", {"percent": percent, "status": status}))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "progress":
                    percent = int(payload["percent"])
                    status = str(payload["status"])
                    self.progress_value.set(percent)
                    self.status_text.set(status)
                    self._log(f"[{percent}%] {status}")
                elif event == "done":
                    result = payload["result"]
                    self.progress_value.set(100)
                    self.status_text.set("Completed")
                    self._log(f"Completed: {result.lead_count} lead(s)")
                    self._log(f"Saved to: {result.output_path}")
                    for key, message in result.source_errors.items():
                        self._log(f"Warning - source '{key}': {message}")
                    if result.no_results_message:
                        self._log(result.no_results_message)
                        messagebox.showwarning("No leads", result.no_results_message)
                    else:
                        messagebox.showinfo(
                            "Completed",
                            f"Collected {result.lead_count} lead(s)\nSaved to:\n{result.output_path}",
                        )
                    self.start_button.configure(state=tk.NORMAL)
                elif event == "error":
                    self.status_text.set("Failed")
                    self._log("Run failed.")
                    self._log(payload["message"])
                    self.start_button.configure(state=tk.NORMAL)
                    messagebox.showerror(
                        "Run failed",
                        f"{payload['message']}\n\nCheck the log area for details.",
                    )
                elif event == "update_available":
                    info: UpdateInfo = payload["info"]
                    self._handle_update_available(info)
                elif event == "update_none":
                    message = str(payload.get("message", "")).strip()
                    if message:
                        self._log(message)
                elif event == "update_error":
                    message = str(payload.get("message", "")).strip()
                    if message:
                        self._log(f"Update check skipped: {message}")
                elif event == "update_downloaded":
                    staged_path = payload["staged_path"]
                    self._log("Update downloaded. Applying update and restarting app...")
                    apply_update_and_restart(staged_path)
                    self.root.after(500, self.root.destroy)
                elif event == "update_apply_error":
                    messagebox.showerror("Update failed", str(payload.get("message", "Unknown error")))
                    self._log(f"Update failed: {payload.get('message', 'Unknown error')}")
        except queue.Empty:
            pass
        finally:
            self.root.after(150, self._poll_events)

    def _log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _start_update_check(self) -> None:
        thread = threading.Thread(target=self._check_updates_worker, daemon=True)
        thread.start()

    def _check_updates_worker(self) -> None:
        if not is_frozen_app():
            self.events.put(
                (
                    "update_none",
                    {
                        "message": "Update check disabled in source mode. It will work in the packaged .exe.",
                    },
                )
            )
            return

        try:
            info = check_for_update(APP_VERSION)
            if info is None:
                config_path = get_update_config_path()
                if not config_path.exists():
                    self.events.put(
                        (
                            "update_none",
                            {
                                "message": (
                                    f"No update config found at {config_path}. "
                                    "Create it to enable self-updates."
                                ),
                            },
                        )
                    )
                return
            self.events.put(("update_available", {"info": info}))
        except Exception as exc:
            self.events.put(("update_error", {"message": str(exc)}))

    def _handle_update_available(self, info: UpdateInfo) -> None:
        answer = messagebox.askyesno(
            "Update Available",
            (
                f"A new version is available: v{info.version}\n"
                f"Current version: v{APP_VERSION}\n\n"
                f"{info.notes or 'Do you want to download and apply the update now?'}"
            ),
        )
        if not answer:
            self._log("Update postponed by user.")
            return
        self._log(f"Downloading update v{info.version}...")
        thread = threading.Thread(target=self._download_update_worker, args=(info,), daemon=True)
        thread.start()

    def _download_update_worker(self, info: UpdateInfo) -> None:
        try:
            staged_path = download_update_binary(info)
            self.events.put(("update_downloaded", {"staged_path": staged_path}))
        except Exception as exc:
            self.events.put(("update_apply_error", {"message": str(exc)}))


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    TrustBridgeApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
