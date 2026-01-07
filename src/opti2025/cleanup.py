from __future__ import annotations

import os
import shutil
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CleanupResult:
    scanned: int
    moved: int
    failed: int
    skipped: int
    backup_dir: Path | None
    errors: tuple[str, ...]


def _collect_temp_dirs() -> list[Path]:
    temp_dirs: list[Path] = []
    env_temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if env_temp:
        temp_dirs.append(Path(env_temp))

    windir = os.environ.get("WINDIR")
    if windir:
        temp_dirs.append(Path(windir) / "Temp")

    return temp_dirs


def _build_backup_root() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / ".opti2025" / "safe_backups" / timestamp


def _backup_subdir_name(temp_dir: Path) -> str:
    drive = temp_dir.drive.replace(":", "")
    parts = [drive] + [part for part in temp_dir.parts if part not in (temp_dir.drive, temp_dir.root)]
    return "_".join(part for part in parts if part)


def _manifest_path(backup_root: Path) -> Path:
    return backup_root / "manifest.json"


def _write_manifest(backup_root: Path, mapping: dict[str, str]) -> None:
    _manifest_path(backup_root).write_text(json.dumps(mapping, indent=2), encoding="utf-8")


def _read_manifest(backup_root: Path) -> dict[str, str]:
    path = _manifest_path(backup_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_cleanup() -> CleanupResult:
    temp_dirs = _collect_temp_dirs()
    backup_root = _build_backup_root()
    mapping: dict[str, str] = {}

    scanned = 0
    moved = 0
    failed = 0
    skipped = 0
    errors: list[str] = []

    for temp_dir in temp_dirs:
        if not temp_dir.exists():
            skipped += 1
            continue
        if not os.access(temp_dir, os.W_OK | os.R_OK):
            skipped += 1
            errors.append(f"Accès refusé: {temp_dir}")
            continue

        destination_name = _backup_subdir_name(temp_dir)
        destination_root = backup_root / destination_name
        mapping[destination_name] = str(temp_dir)
        destination_root.mkdir(parents=True, exist_ok=True)

        for entry in temp_dir.iterdir():
            scanned += 1
            target = destination_root / entry.name
            try:
                shutil.move(str(entry), str(target))
                moved += 1
            except (OSError, shutil.Error) as exc:
                failed += 1
                errors.append(f"{entry}: {exc}")

    if moved == 0 and failed == 0:
        backup_dir: Path | None = None
    else:
        backup_dir = backup_root
        _write_manifest(backup_root, mapping)

    return CleanupResult(
        scanned=scanned,
        moved=moved,
        failed=failed,
        skipped=skipped,
        backup_dir=backup_dir,
        errors=tuple(errors),
    )


def restore_latest_backup() -> CleanupResult:
    backups_root = Path.home() / ".opti2025" / "safe_backups"
    if not backups_root.exists():
        return CleanupResult(0, 0, 0, 1, None, ("Aucune sauvegarde disponible.",))

    backup_dirs = sorted(
        [path for path in backups_root.iterdir() if path.is_dir()],
        reverse=True,
    )
    if not backup_dirs:
        return CleanupResult(0, 0, 0, 1, None, ("Aucune sauvegarde disponible.",))

    latest_backup = backup_dirs[0]
    manifest = _read_manifest(latest_backup)
    if not manifest:
        return CleanupResult(0, 0, 0, 1, None, ("Manifest de sauvegarde introuvable.",))

    scanned = 0
    moved = 0
    failed = 0
    skipped = 0
    errors: list[str] = []

    for backup_name, destination_str in manifest.items():
        destination = Path(destination_str)
        source_root = latest_backup / backup_name
        if not source_root.exists():
            skipped += 1
            continue
        if not destination.exists():
            try:
                destination.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                skipped += 1
                errors.append(f\"Impossible de recréer {destination}: {exc}\")
                continue

        for entry in source_root.iterdir():
            scanned += 1
            target = destination / entry.name
            try:
                shutil.move(str(entry), str(target))
                moved += 1
            except (OSError, shutil.Error) as exc:
                failed += 1
                errors.append(f\"{entry}: {exc}\")

    return CleanupResult(
        scanned=scanned,
        moved=moved,
        failed=failed,
        skipped=skipped,
        backup_dir=latest_backup,
        errors=tuple(errors),
    )
