from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    import winreg


@dataclass(frozen=True)
class MaxPerformanceResult:
    services_disabled: tuple[str, ...]
    indexing_disabled: bool
    power_scheme_set: bool
    onedrive_disabled: bool
    onedrive_process_stopped: bool
    backup_dir: Path | None
    errors: tuple[str, ...]


SERVICE_TARGETS = {
    # Windows Search indexer (indexation de fichiers)
    "WSearch": "Indexation Windows (Search)",
    # SysMain (Superfetch) : préchargement d'applications, non critique
    "SysMain": "Optimisation de préchargement (SysMain)",
    # Diagnostics Tracking Service : télémétrie non essentielle
    "DiagTrack": "Diagnostics et télémétrie (DiagTrack)",
}


def _ensure_windows() -> tuple[bool, list[str]]:
    if sys.platform != "win32":
        return False, ["Profil Max Performance disponible uniquement sur Windows."]
    return True, []


def _backup_root() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / ".opti2025" / "max_backups" / timestamp


def _manifest_path(backup_root: Path) -> Path:
    return backup_root / "manifest.json"


def _write_manifest(backup_root: Path, data: dict[str, object]) -> None:
    _manifest_path(backup_root).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_manifest(backup_root: Path) -> dict[str, object]:
    path = _manifest_path(backup_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _query_service_start_type(service_name: str) -> str | None:
    result = _run_command(["sc.exe", "qc", service_name])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if "START_TYPE" in line:
            match = re.search(r"START_TYPE\\s*:\\s*\\d+\\s+(\\w+)", line)
            if match:
                return match.group(1)
    return None


def _query_service_running(service_name: str) -> bool | None:
    result = _run_command(["sc.exe", "query", service_name])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if "STATE" in line:
            return "RUNNING" in line
    return None


def _set_service_start_type(service_name: str, start_type: str) -> bool:
    result = _run_command(["sc.exe", "config", service_name, f"start={start_type}"])
    return result.returncode == 0


def _normalize_start_type(start_type: str) -> str:
    mapping = {
        "AUTO_START": "auto",
        "DEMAND_START": "demand",
        "DISABLED": "disabled",
        "AUTO": "auto",
        "DEMAND": "demand",
    }
    return mapping.get(start_type.upper(), start_type.lower())


def _stop_service(service_name: str) -> bool:
    result = _run_command(["sc.exe", "stop", service_name])
    return result.returncode == 0


def _start_service(service_name: str) -> bool:
    result = _run_command(["sc.exe", "start", service_name])
    return result.returncode == 0


def _disable_onedrive_run() -> tuple[bool, str | None, list[str]]:
    errors: list[str] = []
    onedrive_value: str | None = None
    disabled = False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        ) as key:
            try:
                onedrive_value, _ = winreg.QueryValueEx(key, "OneDrive")
                winreg.DeleteValue(key, "OneDrive")
                disabled = True
            except FileNotFoundError:
                onedrive_value = None
    except OSError as exc:
        errors.append(f"Impossible de modifier l'entrée OneDrive: {exc}")
    return disabled, onedrive_value, errors


def _restore_onedrive_run(previous_value: str | None) -> list[str]:
    errors: list[str] = []
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if previous_value is None:
                try:
                    winreg.DeleteValue(key, "OneDrive")
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(key, "OneDrive", 0, winreg.REG_SZ, previous_value)
    except OSError as exc:
        errors.append(f"Impossible de restaurer OneDrive: {exc}")
    return errors


def _stop_onedrive_process() -> tuple[bool, list[str]]:
    result = _run_command(["taskkill", "/IM", "OneDrive.exe", "/F"])
    if result.returncode == 0:
        return True, []
    if result.stderr:
        return False, [result.stderr.strip()]
    return False, []


def _get_active_power_scheme() -> str | None:
    result = _run_command(["powercfg", "/getactivescheme"])
    if result.returncode != 0:
        return None
    match = re.search(r"GUID:\\s*([0-9a-fA-F-]+)", result.stdout)
    if match:
        return match.group(1)
    return None


def _find_high_performance_scheme() -> str | None:
    result = _run_command(["powercfg", "/list"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if "High performance" in line or "Performances élevées" in line:
            match = re.search(r"([0-9a-fA-F-]{36})", line)
            if match:
                return match.group(1)
    return None


def _set_power_scheme(scheme_guid: str) -> bool:
    result = _run_command(["powercfg", "/setactive", scheme_guid])
    return result.returncode == 0


def apply_max_performance_profile() -> MaxPerformanceResult:
    is_windows, errors = _ensure_windows()
    if not is_windows:
        return MaxPerformanceResult((), False, False, False, False, None, tuple(errors))

    backup_root = _backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)
    service_states: dict[str, dict[str, object]] = {}

    services_disabled: list[str] = []
    indexing_disabled = False

    for service_name in SERVICE_TARGETS:
        start_type = _query_service_start_type(service_name)
        running = _query_service_running(service_name)
        if start_type is None or running is None:
            errors.append(f"Impossible de lire l'état du service {service_name}.")
            continue
        service_states[service_name] = {
            "start_type": start_type,
            "was_running": running,
        }
        if running:
            _stop_service(service_name)
        if _set_service_start_type(service_name, "disabled"):
            services_disabled.append(service_name)
            if service_name == "WSearch":
                indexing_disabled = True
        else:
            errors.append(f"Impossible de désactiver le service {service_name}.")

    previous_scheme = _get_active_power_scheme()
    high_perf_scheme = _find_high_performance_scheme()
    power_scheme_set = False
    if high_perf_scheme:
        power_scheme_set = _set_power_scheme(high_perf_scheme)
        if not power_scheme_set:
            errors.append("Impossible d'activer le mode Performances élevées.")
    else:
        errors.append("Mode Performances élevées indisponible sur ce système.")

    onedrive_disabled, onedrive_value, onedrive_errors = _disable_onedrive_run()
    errors.extend(onedrive_errors)

    onedrive_stopped, stop_errors = _stop_onedrive_process()
    errors.extend(stop_errors)

    manifest = {
        "services": service_states,
        "power_scheme": previous_scheme,
        "onedrive_run_value": onedrive_value,
    }
    _write_manifest(backup_root, manifest)

    return MaxPerformanceResult(
        services_disabled=tuple(services_disabled),
        indexing_disabled=indexing_disabled,
        power_scheme_set=power_scheme_set,
        onedrive_disabled=onedrive_disabled,
        onedrive_process_stopped=onedrive_stopped,
        backup_dir=backup_root,
        errors=tuple(errors),
    )


def restore_latest_max_performance() -> MaxPerformanceResult:
    is_windows, errors = _ensure_windows()
    if not is_windows:
        return MaxPerformanceResult((), False, False, False, False, None, tuple(errors))

    backups_root = Path.home() / ".opti2025" / "max_backups"
    if not backups_root.exists():
        return MaxPerformanceResult((), False, False, False, False, None, ("Aucune sauvegarde disponible.",))

    backup_dirs = sorted(
        [path for path in backups_root.iterdir() if path.is_dir()],
        reverse=True,
    )
    if not backup_dirs:
        return MaxPerformanceResult((), False, False, False, False, None, ("Aucune sauvegarde disponible.",))

    latest_backup = backup_dirs[0]
    manifest = _read_manifest(latest_backup)
    if not manifest:
        return MaxPerformanceResult((), False, False, False, False, latest_backup, ("Manifest introuvable.",))

    restore_errors: list[str] = []

    services_state = manifest.get("services")
    if isinstance(services_state, dict):
        for service_name, state in services_state.items():
            if not isinstance(state, dict):
                continue
            start_type = state.get("start_type")
            was_running = state.get("was_running")
            if isinstance(start_type, str):
                normalized = _normalize_start_type(start_type)
                if not _set_service_start_type(service_name, normalized):
                    restore_errors.append(
                        f"Impossible de restaurer le service {service_name}."
                    )
            if was_running is True:
                _start_service(service_name)

    power_scheme = manifest.get("power_scheme")
    if isinstance(power_scheme, str):
        if not _set_power_scheme(power_scheme):
            restore_errors.append("Impossible de restaurer le plan d'alimentation.")

    onedrive_value = manifest.get("onedrive_run_value")
    if not isinstance(onedrive_value, str):
        onedrive_value = None
    restore_errors.extend(_restore_onedrive_run(onedrive_value))

    return MaxPerformanceResult(
        services_disabled=(),
        indexing_disabled=False,
        power_scheme_set=False,
        onedrive_disabled=False,
        onedrive_process_stopped=False,
        backup_dir=latest_backup,
        errors=tuple(restore_errors),
    )
