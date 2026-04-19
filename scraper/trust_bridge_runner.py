from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from scraper.sources import get_source
from scraper.trust_bridge import (
    TrustBridgeOptions,
    export_trust_bridge_leads_csv,
    build_trust_bridge_leads,
)

ProgressCallback = Callable[[int, str], None]
CancelRequested = Callable[[], bool]


class RunCancelledError(Exception):
    """Raised when a user stops an in-flight run."""


@dataclass(frozen=True, slots=True)
class TrustBridgeRunConfig:
    source_keys: list[str]
    states: tuple[str, ...]
    per_source_limit: int
    final_limit: int
    city: str | None
    output_path: Path
    allow_missing_phone: bool
    prefer_owner_occupied: bool
    free_phone_lookup_enabled: bool = True
    free_phone_lookup_use_browser: bool = True
    free_phone_lookup_timeout_seconds: float = 10.0
    free_phone_lookup_delay_seconds: float = 0.2
    free_phone_lookup_max_candidates: int = 5
    free_phone_lookup_max_per_run: int = 200


@dataclass(frozen=True, slots=True)
class TrustBridgeRunResult:
    output_path: Path
    lead_count: int
    source_errors: dict[str, str]
    no_results_message: str


def parse_source_keys(value: str) -> list[str]:
    keys = [key.strip() for key in value.split(",") if key.strip()]
    if not keys:
        raise ValueError("At least one source key is required.")
    return keys


def parse_state_codes(values: list[str]) -> tuple[str, ...]:
    clean = tuple(code.strip().upper() for code in values if code.strip())
    if not clean:
        raise ValueError("At least one state code is required.")
    return clean


def run_trust_bridge(
    config: TrustBridgeRunConfig,
    *,
    progress: ProgressCallback | None = None,
    cancel_requested: CancelRequested | None = None,
) -> TrustBridgeRunResult:
    if config.per_source_limit <= 0:
        raise ValueError("--per-source-limit must be greater than 0.")
    if config.final_limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    report_progress(progress, 3, "Validating settings...")
    ensure_not_cancelled(cancel_requested)

    source_to_records = {}
    source_errors: dict[str, str] = {}

    total_sources = len(config.source_keys)
    for index, source_key in enumerate(config.source_keys, start=1):
        ensure_not_cancelled(cancel_requested)
        report_progress(
            progress,
            5 + int(((index - 1) / max(total_sources, 1)) * 60),
            f"Fetching source {index}/{total_sources}: {source_key}",
        )
        try:
            source = get_source(source_key)
            source_to_records[source_key] = source.fetch(
                limit=config.per_source_limit,
                city=config.city,
            )
        except Exception as exc:
            source_errors[source_key] = str(exc)

        report_progress(
            progress,
            5 + int((index / max(total_sources, 1)) * 60),
            (
                f"Finished source {index}/{total_sources}: {source_key}"
                f" ({len(source_to_records.get(source_key, []))} record(s))"
            ),
        )

    if not source_to_records:
        details = "; ".join(f"{key}: {msg}" for key, msg in source_errors.items())
        raise ValueError(f"All requested sources failed. {details}")

    report_progress(progress, 72, "Applying filters and deduplication...")
    ensure_not_cancelled(cancel_requested)

    options = TrustBridgeOptions(
        allowed_states=config.states,
        require_dialable_phone=not config.allow_missing_phone,
        prefer_owner_occupied=config.prefer_owner_occupied,
        free_phone_lookup_enabled=config.free_phone_lookup_enabled,
        free_phone_lookup_use_browser=config.free_phone_lookup_use_browser,
        free_phone_lookup_timeout_seconds=config.free_phone_lookup_timeout_seconds,
        free_phone_lookup_delay_seconds=config.free_phone_lookup_delay_seconds,
        free_phone_lookup_max_candidates=config.free_phone_lookup_max_candidates,
        free_phone_lookup_max_per_run=config.free_phone_lookup_max_per_run,
    )
    total_records = sum(len(records) for records in source_to_records.values())

    def on_build_progress(processed: int, total: int, status: str) -> None:
        ensure_not_cancelled(cancel_requested)
        bounded_total = max(total, total_records, 1)
        phase_progress = min(max(processed, 0), bounded_total) / bounded_total
        report_progress(progress, 72 + int(phase_progress * 17), status)

    try:
        leads = build_trust_bridge_leads(
            source_to_records=source_to_records,
            final_limit=config.final_limit,
            options=options,
            progress=on_build_progress,
            should_cancel=cancel_requested,
        )
    except InterruptedError as exc:
        raise RunCancelledError("Run stopped by user.") from exc

    report_progress(progress, 90, "Exporting results...")
    ensure_not_cancelled(cancel_requested)

    if config.output_path.suffix.lower() == ".xlsx":
        export_trust_bridge_leads_xlsx(leads, config.output_path)
    else:
        export_trust_bridge_leads_csv(leads, config.output_path)

    report_progress(progress, 100, "Completed.")

    no_results_message = ""
    if len(leads) == 0:
        no_results_message = (
            "No leads passed the current filters. "
            "Try increasing fetch limit, or enable missing phone if public lookup has no matches."
        )

    return TrustBridgeRunResult(
        output_path=config.output_path,
        lead_count=len(leads),
        source_errors=source_errors,
        no_results_message=no_results_message,
    )


def export_trust_bridge_leads_xlsx(leads, output_path: Path) -> Path:
    import pandas as pd

    payload = []
    for lead in leads:
        row = lead.to_dict()
        row["raw"] = row["raw"] if isinstance(row["raw"], str) else str(row["raw"])
        payload.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(payload).to_excel(output_path, index=False)
    return output_path


def report_progress(progress: ProgressCallback | None, percent: int, status: str) -> None:
    if progress is None:
        return
    progress(max(0, min(100, int(percent))), status)


def ensure_not_cancelled(cancel_requested: CancelRequested | None) -> None:
    if cancel_requested and cancel_requested():
        raise RunCancelledError("Run stopped by user.")
