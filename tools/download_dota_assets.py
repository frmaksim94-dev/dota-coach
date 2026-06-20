from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dota_api import OpenDotaClient  # noqa: E402
from dota_catalog import download_catalog_assets, get_hero_catalog, get_item_catalog  # noqa: E402


def main() -> int:
    print("Dota Coach AI: downloading real hero/item icons from OpenDota/Steam CDN...")
    client = OpenDotaClient()
    heroes = get_hero_catalog(client)
    items = get_item_catalog(client)
    stats = download_catalog_assets(heroes, items, client)
    print(
        "Done. Hero icons downloaded: {hero_downloaded}/{hero_total}; "
        "item icons downloaded: {item_downloaded}/{item_total}.".format(**stats)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
