from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app_paths import user_data_dir


def _profiles_path() -> Path:
    path = user_data_dir() / "profiles.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_profiles() -> list[dict[str, str]]:
    path = _profiles_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    profiles: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        steam_id = str(row.get("steam_id") or "").strip()
        if not steam_id:
            continue
        name = str(row.get("name") or f"Игрок {steam_id[-4:]}").strip()
        profiles.append({"name": name, "steam_id": steam_id})
    return profiles


def save_profiles(profiles: list[dict[str, str]]) -> None:
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in profiles:
        steam_id = str(row.get("steam_id") or "").strip()
        if not steam_id or steam_id in seen:
            continue
        seen.add(steam_id)
        clean.append({
            "name": str(row.get("name") or f"Игрок {steam_id[-4:]}").strip(),
            "steam_id": steam_id,
            "updated_at": int(time.time()),
        })
    _profiles_path().write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_profile(name: str, steam_id: str) -> list[dict[str, str]]:
    steam_id = str(steam_id).strip()
    name = str(name).strip() or f"Игрок {steam_id[-4:]}"
    profiles = load_profiles()
    updated = False
    for row in profiles:
        if row.get("steam_id") == steam_id:
            row["name"] = name
            updated = True
            break
    if not updated:
        profiles.append({"name": name, "steam_id": steam_id})
    save_profiles(profiles)
    return load_profiles()


def delete_profile(steam_id: str) -> list[dict[str, str]]:
    steam_id = str(steam_id).strip()
    profiles = [row for row in load_profiles() if row.get("steam_id") != steam_id]
    save_profiles(profiles)
    return load_profiles()
