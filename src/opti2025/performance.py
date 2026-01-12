from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    import subprocess
    import winreg


@dataclass(frozen=True)
class PerformanceResult:
    onedrive_disabled: bool
    background_apps_disabled: bool
    onedrive_process_stopped: bool
    backup_dir: Path | None
    errors: tuple[str, ...]


def _ensure_windows() -> tuple[bool, list[str]]:
    if sys.platform != "win32":
        return False, ["Profil Performance disponible uniquement sur Windows."]
    return True, []


def _backup_root() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / ".opti2025" / "performance_backups" / timestamp


def _manifest_path(backup_root: Path) -> Path:
    return backup_root / "manifest.json"


def _write_manifest(backup_root: Path, data: dict[str, object]) -> None:
    _manifest_path(backup_root).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_manifest(backup_root: Path) -> dict[str, object]:
    path = _manifest_path(backup_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _disable_background_apps() -> tuple[bool, int | None, list[str]]:
    errors: list[str] = []
    previous_value: int | None = None
    disabled = False
    try:
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
        ) as key:
            try:
                previous_value, _ = winreg.QueryValueEx(key, "GlobalUserDisabled")
            except FileNotFoundError:
                previous_value = None
            winreg.SetValueEx(key, "GlobalUserDisabled", 0, winreg.REG_DWORD, 1)
            disabled = True
    except OSError as exc:
        errors.append(f"Impossible de réduire les apps en arrière-plan: {exc}")
    return disabled, previous_value, errors


def _restore_background_apps(previous_value: int | None) -> list[str]:
    errors: list[str] = []
    try:
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
        ) as key:
            if previous_value is None:
                try:
                    winreg.DeleteValue(key, "GlobalUserDisabled")
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(
                    key, "GlobalUserDisabled", 0, winreg.REG_DWORD, previous_value
                )
    except OSError as exc:
        errors.append(f"Impossible de restaurer les apps en arrière-plan: {exc}")
    return errors


def _stop_onedrive_process() -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        completed = subprocess.run(
            ["taskkill", "/IM", "OneDrive.exe", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        stopped = completed.returncode == 0
        if not stopped and completed.stderr:
            errors.append(completed.stderr.strip())
        return stopped, errors
    except OSError as exc:
        errors.append(f"Impossible d'arrêter OneDrive: {exc}")
        return False, errors


def apply_performance_profile() -> PerformanceResult:
    is_windows, errors = _ensure_windows()
    if not is_windows:
        return PerformanceResult(False, False, False, None, tuple(errors))

    backup_root = _backup_root()
    backup_root.mkdir(parents=True, exist_ok=True)

    onedrive_disabled, onedrive_value, onedrive_errors = _disable_onedrive_run()
    errors.extend(onedrive_errors)

    background_disabled, background_previous, background_errors = _disable_background_apps()
    errors.extend(background_errors)

    onedrive_stopped, stop_errors = _stop_onedrive_process()
    errors.extend(stop_errors)

    manifest = {
        "onedrive_run_value": onedrive_value,
        "background_previous": background_previous,
    }
    _write_manifest(backup_root, manifest)

    return PerformanceResult(
        onedrive_disabled=onedrive_disabled,
        background_apps_disabled=background_disabled,
        onedrive_process_stopped=onedrive_stopped,
        backup_dir=backup_root,
        errors=tuple(errors),
    )


def restore_latest_performance() -> PerformanceResult:
    is_windows, errors = _ensure_windows()
    if not is_windows:
        return PerformanceResult(False, False, False, None, tuple(errors))

    backups_root = Path.home() / ".opti2025" / "performance_backups"
    if not backups_root.exists():
        return PerformanceResult(False, False, False, None, ("Aucune sauvegarde disponible.",))

    backup_dirs = sorted(
        [path for path in backups_root.iterdir() if path.is_dir()],
        reverse=True,
    )
    if not backup_dirs:
        return PerformanceResult(False, False, False, None, ("Aucune sauvegarde disponible.",))

    latest_backup = backup_dirs[0]
    manifest = _read_manifest(latest_backup)
    if not manifest:
        return PerformanceResult(False, False, False, latest_backup, ("Manifest introuvable.",))

    restore_errors: list[str] = []
    onedrive_value = manifest.get("onedrive_run_value")
    if not isinstance(onedrive_value, str):
        onedrive_value = None
    background_value = manifest.get("background_previous")
    if not isinstance(background_value, int):
        background_value = None

    restore_errors.extend(_restore_onedrive_run(onedrive_value))
    restore_errors.extend(_restore_background_apps(background_value))

    return PerformanceResult(
        onedrive_disabled=False,
        background_apps_disabled=False,
        onedrive_process_stopped=False,
        backup_dir=latest_backup,
        errors=tuple(restore_errors),
    )
