from __future__ import annotations

from typing import Any

from dota_api import OpenDotaClient


def get_heroes() -> dict[int, str]:
    heroes = OpenDotaClient().get_heroes()
    return {hero_id: hero.get("localized_name", f"Hero {hero_id}") for hero_id, hero in heroes.items()}


def get_hero_data() -> dict[int, dict[str, Any]]:
    return OpenDotaClient().get_heroes()
