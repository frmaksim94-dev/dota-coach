from __future__ import annotations

import os
import sys
from pathlib import Path

APP_SLUG = "DotaCoachAI"


def is_frozen() -> bool:
    """True when the app is running from a PyInstaller build."""
    return bool(getattr(sys, "frozen", False))


def app_base_dir() -> Path:
    """
    Folder that contains bundled read-only resources.

    - In source mode this is the project folder.
    - In PyInstaller mode this is the temporary bundle folder, sys._MEIPASS.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Return a path to a bundled resource such as an icon, image, or cfg template."""
    return app_base_dir().joinpath(*parts)


def user_data_dir() -> Path:
    """Writable per-user app folder for files created by the packaged app."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / APP_SLUG
    path.mkdir(parents=True, exist_ok=True)
    return path


def writable_config_dir() -> Path:
    """
    Folder for generated cfg files.

    Source mode writes to ./config as before. Packaged mode writes to the
    user's app-data folder so the exe can live in Program Files or Downloads.
    """
    if is_frozen():
        path = user_data_dir() / "config"
    else:
        path = app_base_dir() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def writable_config_path(filename: str) -> Path:
    return writable_config_dir() / filename


def _manual_gsi_dirs_file() -> Path:
    return writable_config_dir() / "manual_gsi_dirs.txt"


def remember_manual_gsi_dir(path: str | Path) -> None:
    """Remember a manually selected Dota cfg folder for future diagnostics."""
    folder = Path(path).expanduser().resolve(strict=False)
    existing = _remembered_manual_gsi_dirs()
    if folder not in existing:
        existing.append(folder)
    _manual_gsi_dirs_file().write_text("\n".join(str(x) for x in existing), encoding="utf-8")


def _remembered_manual_gsi_dirs() -> list[Path]:
    file_path = _manual_gsi_dirs_file()
    if not file_path.exists():
        return []
    result: list[Path] = []
    try:
        for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            value = line.strip()
            if not value:
                continue
            path = Path(value).expanduser().resolve(strict=False)
            if path.exists():
                _add_unique(result, path)
    except OSError:
        return []
    return result


def _add_unique(paths: list[Path], path: Path) -> None:
    try:
        resolved = path.expanduser().resolve(strict=False)
    except OSError:
        resolved = path.expanduser()
    if resolved not in paths:
        paths.append(resolved)


def _candidate_steam_roots() -> list[Path]:
    """Likely Steam install roots. Environment variables are checked first."""
    roots: list[Path] = []
    for key in ("STEAM_DIR", "STEAM_PATH"):
        value = os.environ.get(key)
        if value:
            _add_unique(roots, Path(value))

    if os.name == "nt":
        for value in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if value:
                _add_unique(roots, Path(value) / "Steam")
        for drive in ("C", "D", "E", "F", "G", "H"):
            _add_unique(roots, Path(f"{drive}:/Steam"))
            _add_unique(roots, Path(f"{drive}:/SteamLibrary"))
    elif sys.platform == "darwin":
        _add_unique(roots, Path.home() / "Library/Application Support/Steam")
    else:
        _add_unique(roots, Path.home() / ".steam/steam")
        _add_unique(roots, Path.home() / ".local/share/Steam")
    return roots


def _steam_library_paths() -> list[Path]:
    """Return Steam library roots, including custom libraries from libraryfolders.vdf."""
    libraries: list[Path] = []
    for root in _candidate_steam_roots():
        if (root / "steamapps").exists():
            _add_unique(libraries, root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if not vdf.exists():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith('"path"'):
                continue
            parts = stripped.split('"')
            if len(parts) >= 4:
                value = parts[3].replace('\\\\', '\\')
                path = Path(value)
                if (path / "steamapps").exists():
                    _add_unique(libraries, path)
    return libraries


def find_dota_cfg_dirs(create: bool = False) -> list[Path]:
    """Find Dota 2 cfg folders that can load gamestate_integration_*.cfg.

    Important: the GSI cfg file must be placed directly inside a Dota cfg folder,
    for example:
        steamapps/common/dota 2 beta/game/dota/cfg/gamestate_integration_dota_coach.cfg

    Older instructions sometimes put the file into cfg/gamestate_integration/.
    That subfolder is not where Dota normally scans GSI files, so this function
    returns the direct cfg directories.

    Set DOTA2_GSI_DIR to override detection. Point it to the cfg folder itself,
    not to a nested gamestate_integration folder.
    """
    dirs: list[Path] = []
    override = os.environ.get("DOTA2_GSI_DIR")
    if override:
        path = Path(override)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if path.exists():
            _add_unique(dirs, path)

    for path in _remembered_manual_gsi_dirs():
        if path.exists():
            _add_unique(dirs, path)

    for library in _steam_library_paths():
        dota_root = library / "steamapps" / "common" / "dota 2 beta"
        if not dota_root.exists():
            continue
        for cfg_base in (dota_root / "game" / "dota" / "cfg", dota_root / "dota" / "cfg"):
            if cfg_base.exists() or create:
                if create:
                    cfg_base.mkdir(parents=True, exist_ok=True)
                if cfg_base.exists():
                    _add_unique(dirs, cfg_base)
    return dirs


def find_dota_gsi_dirs(create: bool = False) -> list[Path]:
    """Backward-compatible alias used by older UI code."""
    return find_dota_cfg_dirs(create=create)

def find_dota_gsi_targets(create: bool = False) -> list[Path]:
    """Return every cfg file location worth writing for Dota 2 GSI.

    Some Dota/Steam setups read gamestate_integration_*.cfg directly from
    game/dota/cfg/. Other guides use game/dota/cfg/gamestate_integration/.
    To avoid the common "данных пока нет" problem, the app writes the same cfg
    into both modern and legacy locations when possible.
    """
    filename = "gamestate_integration_dota_coach.cfg"
    targets: list[Path] = []

    override = os.environ.get("DOTA2_GSI_DIR")
    if override:
        base = Path(override)
        if create:
            base.mkdir(parents=True, exist_ok=True)
        if base.exists():
            _add_unique(targets, base / filename)

    for base in _remembered_manual_gsi_dirs():
        if base.exists():
            _add_unique(targets, base / filename)

    for library in _steam_library_paths():
        dota_root = library / "steamapps" / "common" / "dota 2 beta"
        if not dota_root.exists():
            continue
        for cfg_base in (dota_root / "game" / "dota" / "cfg", dota_root / "dota" / "cfg"):
            if cfg_base.exists() or create:
                if create:
                    cfg_base.mkdir(parents=True, exist_ok=True)
                    (cfg_base / "gamestate_integration").mkdir(parents=True, exist_ok=True)
                if cfg_base.exists():
                    _add_unique(targets, cfg_base / filename)
                    _add_unique(targets, cfg_base / "gamestate_integration" / filename)
    return targets


def describe_gsi_installation() -> list[dict[str, str]]:
    """Human-readable GSI cfg diagnostics for the Live Coach tab."""
    rows: list[dict[str, str]] = []
    for target in find_dota_gsi_targets(create=False):
        rows.append(
            {
                "path": str(target),
                "exists": "да" if target.exists() else "нет",
                "folder_exists": "да" if target.parent.exists() else "нет",
            }
        )
    return rows



def asset_cache_dir(*parts: str) -> Path:
    """Writable cache for downloaded hero/item/map images."""
    path = user_data_dir() / "assets_cache"
    if parts:
        path = path.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_cache_path(*parts: str) -> Path:
    if not parts:
        return asset_cache_dir()
    folder = asset_cache_dir(*parts[:-1]) if len(parts) > 1 else asset_cache_dir()
    return folder / parts[-1]
