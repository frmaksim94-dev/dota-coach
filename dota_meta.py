from __future__ import annotations

import time
from typing import Any

from dota_catalog import attr_label, get_hero_catalog, normalize_attr
from dota_api import OpenDotaClient, PlayerSummary

BRACKET_FIELDS = [str(i) for i in range(1, 9)]


def to_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def winrate(wins: int, picks: int) -> float:
    return round(wins / picks * 100, 2) if picks > 0 else 0.0


def build_hero_meta_rows(client: OpenDotaClient) -> list[dict[str, Any]]:
    """Build hero meta table from OpenDota /heroStats with offline fallback."""
    raw_rows = client.get_public_hero_stats()
    rows: list[dict[str, Any]] = []
    if raw_rows:
        for raw in raw_rows:
            name = raw.get("localized_name") or raw.get("dname") or raw.get("name") or "Hero"
            public_picks = 0
            public_wins = 0
            for bracket in BRACKET_FIELDS:
                public_picks += to_int(raw.get(f"{bracket}_pick"))
                public_wins += to_int(raw.get(f"{bracket}_win"))
            if public_picks == 0:
                public_picks = to_int(raw.get("turbo_picks"))
                public_wins = to_int(raw.get("turbo_wins"))
            pro_pick = to_int(raw.get("pro_pick"))
            pro_win = to_int(raw.get("pro_win"))
            rows.append({
                "hero_id": to_int(raw.get("id")),
                "name": str(name),
                "attr": normalize_attr(raw.get("primary_attr")),
                "attr_ru": attr_label(raw.get("primary_attr")),
                "roles": raw.get("roles") if isinstance(raw.get("roles"), list) else [],
                "public_picks": public_picks,
                "public_wins": public_wins,
                "public_wr": winrate(public_wins, public_picks),
                "pro_pick": pro_pick,
                "pro_win": pro_win,
                "pro_wr": winrate(pro_win, pro_pick),
                "source": "OpenDota heroStats",
            })
    else:
        for hero in get_hero_catalog(client):
            rows.append({
                "hero_id": 0,
                "name": hero.get("name", "Hero"),
                "attr": hero.get("attr", "all"),
                "attr_ru": hero.get("attr_ru", "Универсальность"),
                "roles": hero.get("roles", []),
                "public_picks": 0,
                "public_wins": 0,
                "public_wr": 0.0,
                "pro_pick": 0,
                "pro_win": 0,
                "pro_wr": 0.0,
                "source": "offline fallback",
            })
    rows.sort(key=lambda row: (float(row.get("public_wr") or 0), int(row.get("public_picks") or 0)), reverse=True)
    return rows


def match_history_rows(summary: PlayerSummary) -> list[dict[str, Any]]:
    heroes_by_id = summary.heroes_by_id or {}
    perf_by_match = {int(p.get("match_id") or 0): p for p in summary.performances or []}
    rows: list[dict[str, Any]] = []
    for recent in summary.recent_matches:
        match_id = to_int(recent.get("match_id"))
        perf = perf_by_match.get(match_id, {})
        hero_id = to_int(perf.get("hero_id") or recent.get("hero_id"))
        hero = heroes_by_id.get(hero_id, {})
        duration = to_int(perf.get("duration") or recent.get("duration"))
        win = bool(perf.get("win")) if perf else _recent_win(recent)
        kills = to_int(perf.get("kills") if perf else recent.get("kills"))
        deaths = to_int(perf.get("deaths") if perf else recent.get("deaths"))
        assists = to_int(perf.get("assists") if perf else recent.get("assists"))
        rows.append({
            "match_id": match_id,
            "date": format_date(perf.get("start_time") if perf else recent.get("start_time")),
            "hero": hero.get("localized_name") or f"Hero {hero_id or '—'}",
            "result": "Победа" if win else "Поражение",
            "duration": format_duration(duration),
            "kda": f"{kills}/{deaths}/{assists}",
            "gpm_xpm": _pair(perf.get("gold_per_min"), perf.get("xp_per_min")) if perf else "—",
            "lh_dn": _pair(perf.get("last_hits"), perf.get("denies")) if perf else "—",
            "source": perf.get("source", "recent") if perf else "recent",
            "raw": perf or recent,
        })
    return rows


def _recent_win(match: dict[str, Any]) -> bool:
    radiant_win = bool(match.get("radiant_win"))
    player_slot = to_int(match.get("player_slot"))
    is_radiant = player_slot < 128
    return (radiant_win and is_radiant) or ((not radiant_win) and (not is_radiant))


def _pair(a: Any, b: Any) -> str:
    aa = to_int(a)
    bb = to_int(b)
    if aa == 0 and bb == 0:
        return "—"
    return f"{aa}/{bb}"


def format_duration(seconds: Any) -> str:
    value = to_int(seconds)
    if value <= 0:
        return "—"
    return f"{value // 60}:{value % 60:02d}"


def format_date(timestamp: Any) -> str:
    value = to_int(timestamp)
    if value <= 0:
        return "—"
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(value))
