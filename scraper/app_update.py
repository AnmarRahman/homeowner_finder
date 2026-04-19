from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

APP_NAME = "TrustBridgeLeadBuilder"
APP_VERSION = "1.0.4"
UPDATE_CONFIG_FILENAME = "update_config.json"
DEFAULT_MANIFEST_URL = "https://trustbridge-manifest.vercel.app/latest.json"


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    url: str
    notes: str = ""
    sha256: str = ""


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_manifest_url() -> str:
    env_url = os.getenv("TRUST_BRIDGE_UPDATE_MANIFEST_URL", "").strip()
    if env_url:
        return env_url

    config_path = get_update_config_path()
    if not config_path.exists():
        return DEFAULT_MANIFEST_URL
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_MANIFEST_URL
    if not isinstance(payload, dict):
        return DEFAULT_MANIFEST_URL
    configured = str(payload.get("manifest_url", "")).strip()
    return configured or DEFAULT_MANIFEST_URL


def get_update_config_path() -> Path:
    if is_frozen_app():
        return Path(sys.executable).resolve().parent / UPDATE_CONFIG_FILENAME
    return Path.cwd() / UPDATE_CONFIG_FILENAME


def check_for_update(current_version: str, timeout_seconds: int = 12) -> UpdateInfo | None:
    manifest_url = get_manifest_url()
    if not manifest_url:
        return None

    response = requests.get(
        manifest_url,
        headers={"Accept": "application/json"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return None

    latest_version = str(payload.get("version", "")).strip()
    download_url = str(payload.get("url", "")).strip()
    if not latest_version or not download_url:
        return None

    if not is_newer_version(latest_version, current_version):
        return None

    return UpdateInfo(
        version=latest_version,
        url=download_url,
        notes=str(payload.get("notes", "")).strip(),
        sha256=str(payload.get("sha256", "")).strip().lower(),
    )


def is_newer_version(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def parse_version(value: str) -> tuple[int, ...]:
    numbers: list[int] = []
    chunk = ""
    for char in value:
        if char.isdigit():
            chunk += char
        else:
            if chunk:
                numbers.append(int(chunk))
                chunk = ""
    if chunk:
        numbers.append(int(chunk))
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers[:3])


def download_update_binary(update: UpdateInfo, timeout_seconds: int = 30) -> Path:
    if not is_frozen_app():
        raise RuntimeError("Self-update is only supported from the packaged .exe.")

    exe_dir = Path(sys.executable).resolve().parent
    url_name = Path(urlparse(update.url).path).name or f"{APP_NAME}.exe"
    staged_name = f"{Path(url_name).stem}.new.exe"
    staged_path = exe_dir / staged_name

    with requests.get(update.url, stream=True, timeout=timeout_seconds) as response:
        response.raise_for_status()
        with staged_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    handle.write(chunk)

    if update.sha256:
        actual = sha256_file(staged_path)
        if actual.lower() != update.sha256.lower():
            staged_path.unlink(missing_ok=True)
            raise RuntimeError("Downloaded update failed checksum verification.")

    return staged_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def apply_update_and_restart(staged_exe: Path) -> None:
    if not is_frozen_app():
        raise RuntimeError("Self-update is only supported from the packaged .exe.")

    current_exe = Path(sys.executable).resolve()
    script_path = write_update_script(current_exe=current_exe, staged_exe=staged_exe)

    subprocess.Popen(
        ["cmd", "/c", str(script_path)],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )


def write_update_script(current_exe: Path, staged_exe: Path) -> Path:
    tmp = Path(tempfile.gettempdir())
    stamp = int(time.time() * 1000)
    script_path = tmp / f"tb_update_{stamp}.bat"

    script = (
        "@echo off\n"
        "setlocal\n"
        f"set CURRENT_EXE={quote_cmd_path(current_exe)}\n"
        f"set STAGED_EXE={quote_cmd_path(staged_exe)}\n"
        "set RETRIES=0\n"
        ":retry\n"
        "timeout /t 1 /nobreak >nul\n"
        "move /Y %STAGED_EXE% %CURRENT_EXE% >nul 2>&1\n"
        "if errorlevel 1 (\n"
        "  set /a RETRIES+=1\n"
        "  if %RETRIES% GEQ 20 goto failed\n"
        "  goto retry\n"
        ")\n"
        "start \"\" %CURRENT_EXE%\n"
        "del \"%~f0\"\n"
        "exit /b 0\n"
        ":failed\n"
        "echo Update failed. Could not replace executable.\n"
        "del \"%~f0\"\n"
        "exit /b 1\n"
    )
    script_path.write_text(script, encoding="utf-8")
    return script_path


def quote_cmd_path(path: Path) -> str:
    return f"\"{str(path)}\""
