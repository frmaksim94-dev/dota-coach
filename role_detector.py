"""Role detection for Dota 2 player profiles.

The detector combines three signals:
1. detailed match lane data when OpenDota match details are available;
2. economy/warding pattern from recent matches;
3. hero pool hints from the player's most played heroes.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

ROLES = ["Carry", "Mid", "Offlane", "Soft Support", "Hard Support"]
ROLE_RU = {
    "Carry": "Керри / Pos 1",
    "Mid": "Мид / Pos 2",
    "Offlane": "Оффлейн / Pos 3",
    "Soft Support": "Саппорт 4",
    "Hard Support": "Саппорт 5",
}

# Curated hero-position hints. They are not absolute: many heroes are flexible,
# therefore these scores are only one part of the final detector.
HERO_HINTS: dict[str, set[int]] = {
    "Carry": {
        1, 4, 6, 8, 10, 12, 15, 18, 32, 35, 41, 44, 46, 48, 54, 56, 63,
        67, 70, 72, 73, 81, 89, 93, 94, 95, 109, 113, 114,
    },
    "Mid": {
        11, 13, 17, 22, 23, 25, 34, 36, 39, 43, 46, 49, 52, 74, 76, 82,
        106, 126,
    },
    "Offlane": {
        2, 16, 28, 29, 38, 51, 55, 60, 69, 78, 96, 97, 98, 99, 104, 108,
        120, 129, 135, 137,
    },
    "Soft Support": {
        7, 9, 14, 19, 51, 62, 71, 86, 88, 100, 101, 105, 107, 110, 123,
        128,
    },
    "Hard Support": {
        3, 5, 20, 26, 27, 30, 31, 37, 50, 57, 64, 66, 68, 75, 79, 83, 85,
        87, 90, 91, 102, 111, 112, 121, 128,
    },
}

LANE_ROLE_NAMES = {
    1: "safe lane",
    2: "mid lane",
    3: "off lane",
    4: "jungle/roam",
}


def detect_role(hero_stats: list[dict[str, Any]], heroes_by_id: dict[int, dict[str, Any]] | None = None,
                performances: list[dict[str, Any]] | None = None) -> str:
    """Backward-compatible helper returning only the role name."""
    return detect_role_detailed(hero_stats, heroes_by_id, performances)["role"]


def detect_role_detailed(
    hero_stats: list[dict[str, Any]] | None,
    heroes_by_id: dict[int, dict[str, Any]] | None = None,
    performances: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scores: defaultdict[str, float] = defaultdict(float)
    reasons: list[str] = []
    hero_stats = hero_stats or []
    heroes_by_id = heroes_by_id or {}
    performances = performances or []

    _score_from_performances(scores, reasons, performances)
    _score_from_hero_pool(scores, reasons, hero_stats, heroes_by_id)

    if not any(scores.values()):
        scores["Carry"] = 1.0
        reasons.append("Недостаточно данных: поставлена роль Carry как нейтральная заглушка.")

    ordered = sorted(((role, float(scores.get(role, 0.0))) for role in ROLES), key=lambda item: item[1], reverse=True)
    role, top_score = ordered[0]
    total = sum(score for _, score in ordered) or 1.0
    confidence = min(0.96, max(0.20, top_score / total))

    return {
        "role": role,
        "role_ru": ROLE_RU.get(role, role),
        "confidence": round(confidence * 100, 1),
        "scores": {role_name: round(score, 2) for role_name, score in ordered},
        "reasons": reasons[:6],
    }


def _score_from_performances(scores: defaultdict[str, float], reasons: list[str], performances: list[dict[str, Any]]) -> None:
    if not performances:
        return

    lane_counter: defaultdict[int, int] = defaultdict(int)
    support_games = 0
    core_games = 0

    for performance in performances:
        lane_role = _to_int(performance.get("lane_role"))
        if lane_role:
            lane_counter[lane_role] += 1

        minutes = max(1.0, float(performance.get("duration") or 0) / 60.0)
        gpm = _to_float(performance.get("gold_per_min"))
        xpm = _to_float(performance.get("xp_per_min"))
        lhpm = _safe_div(_to_float(performance.get("last_hits")), minutes)
        wards = (_to_float(performance.get("obs_placed")) or 0.0) + (_to_float(performance.get("sen_placed")) or 0.0)
        tower_dpm = _safe_div(_to_float(performance.get("tower_damage")), minutes)
        roaming = bool(performance.get("is_roaming"))

        if lane_role == 2:
            scores["Mid"] += 4.0
        elif lane_role == 1:
            if (gpm or 0) >= 420 or lhpm >= 5.0:
                scores["Carry"] += 3.8
            else:
                scores["Hard Support"] += 2.1
        elif lane_role == 3:
            if (gpm or 0) >= 370 or lhpm >= 3.8:
                scores["Offlane"] += 3.3
            else:
                scores["Soft Support"] += 1.9
        elif lane_role == 4 or roaming:
            scores["Soft Support"] += 3.0

        if wards >= 6 and (gpm or 999) < 390:
            support_games += 1
            scores["Hard Support"] += 2.0
            scores["Soft Support"] += 1.2
        elif wards >= 3 and (gpm or 999) < 430:
            support_games += 1
            scores["Soft Support"] += 1.4
            scores["Hard Support"] += 0.8

        if (gpm or 0) >= 500 or lhpm >= 6.2:
            core_games += 1
            scores["Carry"] += 1.8
            if tower_dpm >= 80:
                scores["Carry"] += 0.8
        elif (gpm or 0) >= 430 and (xpm or 0) >= 520:
            core_games += 1
            scores["Mid"] += 0.9
            scores["Offlane"] += 0.6

    if lane_counter:
        top_lane, count = max(lane_counter.items(), key=lambda item: item[1])
        reasons.append(f"Чаще всего OpenDota видит линию: {LANE_ROLE_NAMES.get(top_lane, top_lane)} ({count} матч.).")
    if support_games:
        reasons.append(f"Есть саппорт-паттерн: варды и низкая экономика в {support_games} матчах.")
    if core_games:
        reasons.append(f"Есть кор-паттерн: высокий фарм/экономика в {core_games} матчах.")


def _score_from_hero_pool(
    scores: defaultdict[str, float],
    reasons: list[str],
    hero_stats: list[dict[str, Any]],
    heroes_by_id: dict[int, dict[str, Any]],
) -> None:
    if not hero_stats:
        return

    top_hero_names: list[str] = []
    for row in hero_stats[:12]:
        hero_id = _to_int(row.get("hero_id")) or 0
        games = float(_to_int(row.get("games")) or 0)
        if games <= 0:
            continue
        weight = min(games, 60.0) ** 0.7
        hero = heroes_by_id.get(hero_id, {})
        roles = set(hero.get("roles") or [])
        name = hero.get("localized_name") or f"Hero {hero_id}"
        if len(top_hero_names) < 3:
            top_hero_names.append(str(name))

        for role, hero_ids in HERO_HINTS.items():
            if hero_id in hero_ids:
                scores[role] += 1.7 * weight

        if "Carry" in roles:
            scores["Carry"] += 0.8 * weight
        if "Support" in roles:
            scores["Hard Support"] += 0.75 * weight
            scores["Soft Support"] += 0.65 * weight
        if "Initiator" in roles or "Durable" in roles:
            scores["Offlane"] += 0.35 * weight
            scores["Soft Support"] += 0.15 * weight
        if "Nuker" in roles or "Escape" in roles:
            scores["Mid"] += 0.25 * weight
        if "Pusher" in roles:
            scores["Carry"] += 0.2 * weight
            scores["Offlane"] += 0.2 * weight

    if top_hero_names:
        reasons.append("Пул героев: " + ", ".join(top_hero_names) + ".")


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(a: float | None, b: float | None) -> float:
    if a is None or not b:
        return 0.0
    return float(a) / float(b)
