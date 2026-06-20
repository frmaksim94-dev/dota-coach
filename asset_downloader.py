"""Runtime downloader for real Dota hero/item icons.

The packaged app ships with small fallback icons so it opens immediately. When the
user has internet, this module caches real Valve/OpenDota image assets in the
per-user app folder and the UI starts using them automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from app_paths import asset_cache_dir, asset_cache_path
from config import REQUEST_TIMEOUT
from dota_api import OpenDotaClient
from dota_catalog import slugify

STEAM_CDN = "https://cdn.cloudflare.steamstatic.com"


def _absolute_asset_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        return "https:" + text.split("?", 1)[0]
    if text.startswith(("http://", "https://")):
        return text.split("?", 1)[0]
    if text.startswith("/"):
        return urljoin(STEAM_CDN, text.split("?", 1)[0])
    return text.split("?", 1)[0]


def _download_image(url: str, target: Path) -> bool:
    if not url:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 800:
        return False
    try:
        response = requests.get(url, timeout=max(REQUEST_TIMEOUT, 15), headers={"User-Agent": "DotaCoachAI/0.9"})
        if not response.ok:
            return False
        data = response.content
        # png/jpg/webp; keep validation light because Valve/OpenDota may change headers.
        if len(data) < 800:
            return False
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        return True
    except Exception:
        return False


def cached_asset_count(kind: str) -> int:
    folder = asset_cache_dir(kind)
    return len([p for p in folder.glob("*.png") if p.is_file() and p.stat().st_size > 800])


def download_catalog_assets(client: OpenDotaClient | None = None, limit: int | None = None) -> dict[str, int | str]:
    """Download missing hero and item icons into the writable cache.

    Returns a small stats dictionary. This function is safe to call from a worker
    thread; network failures are reported as counters, not raised.
    """
    client = client or OpenDotaClient()
    stats: dict[str, int | str] = {
        "heroes_downloaded": 0,
        "items_downloaded": 0,
        "heroes_cached": cached_asset_count("heroes"),
        "items_cached": cached_asset_count("items"),
        "errors": 0,
        "source": "OpenDota + Valve CDN",
    }

    # Heroes: /heroStats contains img/icon paths. Prefer wide portraits because
    # they look like the in-game picker and the user's example.
    try:
        heroes = client.get_public_hero_stats()
    except Exception:
        heroes = []
        stats["errors"] = int(stats["errors"]) + 1
    count = 0
    for row in heroes:
        name = str(row.get("localized_name") or "").strip()
        if not name:
            continue
        url = _absolute_asset_url(row.get("img") or row.get("icon"))
        if not url:
            continue
        target = asset_cache_path("heroes", f"{slugify(name)}.png")
        if _download_image(url, target):
            stats["heroes_downloaded"] = int(stats["heroes_downloaded"]) + 1
        count += 1
        if limit and count >= limit:
            break

    # Items: constants/items usually has dname/cost; not every row has an img, so
    # fallback to the known dota_react item URL based on the raw OpenDota key.
    try:
        items = client._get("constants/items", max_age=24 * 3600)
    except Exception:
        items = {}
        stats["errors"] = int(stats["errors"]) + 1
    count = 0
    if isinstance(items, dict):
        for raw_name, row in items.items():
            if not isinstance(row, dict):
                continue
            dname = str(row.get("dname") or row.get("localized_name") or "").strip()
            if not dname or raw_name.startswith("recipe"):
                continue
            target = asset_cache_path("items", f"{slugify(dname)}.png")
            url = _absolute_asset_url(row.get("img"))
            if not url:
                url = f"{STEAM_CDN}/apps/dota2/images/dota_react/items/{raw_name}.png"
            if _download_image(url, target):
                stats["items_downloaded"] = int(stats["items_downloaded"]) + 1
            count += 1
            if limit and count >= limit:
                break

    stats["heroes_cached"] = cached_asset_count("heroes")
    stats["items_cached"] = cached_asset_count("items")
    return stats
