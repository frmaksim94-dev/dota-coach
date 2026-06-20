"""Role benchmarks and pro-style references.

The values below are coaching targets, not live official statistics. They make the
app useful even without paid esports datasets. The UI labels them as role
benchmarks and style references rather than exact current pro averages.
"""

from __future__ import annotations

from typing import Any

PROS = {
    "Carry": ["Yatoro", "Ame", "Watson", "Pure", "Nightfall"],
    "Mid": ["Nisha", "Malr1ne", "Quinn", "Larl", "NothingToSay"],
    "Offlane": ["Collapse", "33", "Ace", "ATF", "zai"],
    "Soft Support": ["Mira", "XinQ", "Save-", "Boxi", "Saksa"],
    "Hard Support": ["Miposhka", "Seleri", "Insania", "Whitemon", "y`"],
}

ROLE_BASELINES: dict[str, dict[str, float]] = {
    "Carry": {
        "avg_gpm": 620,
        "avg_xpm": 700,
        "last_hits_per_min": 8.5,
        "avg_kda": 4.0,
        "avg_deaths": 4.2,
        "hero_damage_per_min": 720,
        "tower_damage_per_min": 105,
        "teamfight_participation": 58,
    },
    "Mid": {
        "avg_gpm": 570,
        "avg_xpm": 660,
        "last_hits_per_min": 6.7,
        "avg_kda": 4.2,
        "avg_deaths": 4.8,
        "hero_damage_per_min": 820,
        "tower_damage_per_min": 70,
        "teamfight_participation": 63,
    },
    "Offlane": {
        "avg_gpm": 470,
        "avg_xpm": 590,
        "last_hits_per_min": 4.8,
        "avg_kda": 3.3,
        "avg_deaths": 5.8,
        "hero_damage_per_min": 670,
        "tower_damage_per_min": 58,
        "teamfight_participation": 66,
        "wards_per_match": 1.6,
    },
    "Soft Support": {
        "avg_gpm": 340,
        "avg_xpm": 440,
        "last_hits_per_min": 1.4,
        "avg_kda": 2.9,
        "avg_deaths": 7.0,
        "hero_damage_per_min": 500,
        "teamfight_participation": 70,
        "wards_per_match": 6.0,
        "camps_stacked_per_match": 1.4,
    },
    "Hard Support": {
        "avg_gpm": 295,
        "avg_xpm": 390,
        "last_hits_per_min": 0.8,
        "avg_kda": 2.5,
        "avg_deaths": 7.4,
        "hero_damage_per_min": 360,
        "teamfight_participation": 68,
        "wards_per_match": 10.0,
        "camps_stacked_per_match": 1.8,
    },
}

METRIC_LABELS = {
    "avg_gpm": "GPM",
    "avg_xpm": "XPM",
    "last_hits_per_min": "Ластхитов/мин",
    "avg_kda": "KDA",
    "avg_deaths": "Смертей/матч",
    "hero_damage_per_min": "Урон героям/мин",
    "tower_damage_per_min": "Урон вышкам/мин",
    "teamfight_participation": "Участие в драках, %",
    "wards_per_match": "Вардов/матч",
    "camps_stacked_per_match": "Стаков/матч",
}

LOWER_IS_BETTER = {"avg_deaths"}

PRO_STYLE_PROFILES: dict[str, list[dict[str, Any]]] = {
    "Carry": [
        {"name": "Yatoro", "style": "гибкий герой-пул, ранние драки + сильный лейт", "weights": {"avg_kda": 0.35, "teamfight_participation": 0.35, "avg_gpm": 0.30}},
        {"name": "Ame", "style": "стабильный фарм, минимум лишнего риска", "weights": {"avg_deaths": 0.40, "last_hits_per_min": 0.35, "avg_gpm": 0.25}},
        {"name": "Watson", "style": "ускоренный экономический темп", "weights": {"avg_gpm": 0.45, "avg_xpm": 0.30, "tower_damage_per_min": 0.25}},
        {"name": "Pure", "style": "агрессивный кор с высоким уроном", "weights": {"hero_damage_per_min": 0.45, "teamfight_participation": 0.30, "avg_kda": 0.25}},
    ],
    "Mid": [
        {"name": "Nisha", "style": "стабильная линия и высокий импакт без лишних смертей", "weights": {"avg_deaths": 0.35, "avg_kda": 0.35, "avg_xpm": 0.30}},
        {"name": "Malr1ne", "style": "давление по карте и высокий урон", "weights": {"hero_damage_per_min": 0.45, "teamfight_participation": 0.30, "avg_gpm": 0.25}},
        {"name": "Quinn", "style": "темповый мид с ранним сноуболлом", "weights": {"avg_xpm": 0.35, "avg_gpm": 0.35, "teamfight_participation": 0.30}},
    ],
    "Offlane": [
        {"name": "Collapse", "style": "инициация и командные драки", "weights": {"teamfight_participation": 0.45, "hero_damage_per_min": 0.30, "avg_kda": 0.25}},
        {"name": "33", "style": "аура-экономика, давление по карте", "weights": {"avg_gpm": 0.35, "tower_damage_per_min": 0.30, "teamfight_participation": 0.35}},
        {"name": "Ace", "style": "стабильная линия и командная полезность", "weights": {"avg_deaths": 0.35, "avg_xpm": 0.30, "teamfight_participation": 0.35}},
    ],
    "Soft Support": [
        {"name": "Mira", "style": "плеймейкинг и участие в драках", "weights": {"teamfight_participation": 0.45, "hero_damage_per_min": 0.25, "avg_kda": 0.30}},
        {"name": "XinQ", "style": "агрессивные перемещения и высокий скилл-импакт", "weights": {"hero_damage_per_min": 0.40, "avg_xpm": 0.25, "teamfight_participation": 0.35}},
        {"name": "Boxi", "style": "пространство, стаки, ранние ротации", "weights": {"camps_stacked_per_match": 0.35, "wards_per_match": 0.25, "teamfight_participation": 0.40}},
    ],
    "Hard Support": [
        {"name": "Miposhka", "style": "видение, дисциплина и сейвы", "weights": {"wards_per_match": 0.40, "avg_deaths": 0.30, "teamfight_participation": 0.30}},
        {"name": "Seleri", "style": "макро, стаки и командная структура", "weights": {"camps_stacked_per_match": 0.35, "wards_per_match": 0.35, "teamfight_participation": 0.30}},
        {"name": "Insania", "style": "позиционка и стабильность в драках", "weights": {"avg_deaths": 0.40, "avg_kda": 0.30, "teamfight_participation": 0.30}},
    ],
}


def get_pros_for_role(role: str) -> list[str]:
    return PROS.get(role, [])


def build_role_comparison(metrics: dict[str, float], role: str) -> list[dict[str, Any]]:
    baseline = ROLE_BASELINES.get(role) or ROLE_BASELINES["Carry"]
    rows: list[dict[str, Any]] = []
    for key, target in baseline.items():
        player_value = float(metrics.get(key, 0.0) or 0.0)
        if player_value <= 0 and key not in {"avg_deaths"}:
            status = "нет данных"
            ratio = 0.0
            delta = 0.0
        else:
            if key in LOWER_IS_BETTER:
                ratio = target / max(player_value, 0.1)
                delta = target - player_value
            else:
                ratio = player_value / max(target, 0.1)
                delta = player_value - target
            status = _grade_ratio(ratio)

        rows.append(
            {
                "metric": key,
                "label": METRIC_LABELS.get(key, key),
                "player": round(player_value, 2),
                "target": round(target, 2),
                "delta": round(delta, 2),
                "ratio": round(ratio, 3),
                "status": status,
                "advice": _metric_advice(key, role, ratio),
            }
        )
    return rows


def style_matches(metrics: dict[str, float], role: str, limit: int = 3) -> list[dict[str, Any]]:
    profiles = PRO_STYLE_PROFILES.get(role, [])
    baseline = ROLE_BASELINES.get(role) or ROLE_BASELINES["Carry"]
    scored: list[dict[str, Any]] = []
    for profile in profiles:
        score = 0.0
        for metric, weight in profile["weights"].items():
            player = float(metrics.get(metric, 0.0) or 0.0)
            target = baseline.get(metric, 1.0)
            if metric in LOWER_IS_BETTER:
                metric_score = min(1.25, target / max(player, 0.1)) if player else 0.5
            else:
                metric_score = min(1.25, player / max(target, 0.1)) if player else 0.5
            score += float(weight) * metric_score
        scored.append({**profile, "similarity": round(min(score, 1.0) * 100, 1)})
    return sorted(scored, key=lambda item: item["similarity"], reverse=True)[:limit]


def generate_focus_plan(comparison: list[dict[str, Any]], role: str) -> list[str]:
    weak = [row for row in comparison if row["status"] in {"проседает", "сильно ниже"}]
    weak.sort(key=lambda row: row["ratio"])
    if not weak:
        return [
            "Основные метрики выглядят близко к ориентиру роли. Следующий шаг — разбирать конкретные смерти и решения на карте по реплеям.",
            "Закрепи сильные стороны: 3-5 героев в пуле, стабильный старт и понятный план на 10/20/30 минуту.",
        ]
    plan = [row["advice"] for row in weak[:4]]
    if role in {"Carry", "Mid"}:
        plan.append("После каждой игры смотри первые 10 минут: пропущенные крипы, ненужные TP и моменты, где можно было забрать объект.")
    elif role == "Offlane":
        plan.append("Отмечай тайминги: когда ты забрал линию, когда заставил саппортов врага прийти к тебе, когда купил первый командный предмет.")
    else:
        plan.append("После игры проверь: варды под цель, смоки до важных таймингов, стаки до 7:00 и смерти без размена.")
    return plan


def _grade_ratio(ratio: float) -> str:
    if ratio >= 1.08:
        return "сильнее ориентира"
    if ratio >= 0.92:
        return "около ориентира"
    if ratio >= 0.72:
        return "проседает"
    return "сильно ниже"


def _metric_advice(metric: str, role: str, ratio: float) -> str:
    if ratio >= 0.92:
        return f"{METRIC_LABELS.get(metric, metric)}: держи текущий уровень, это не главный провал."
    if metric == "avg_gpm":
        return "GPM: заранее планируй следующие 2 лагеря/линию, не бегай без цели и покупай предметы под ближайший файт."
    if metric == "avg_xpm":
        return "XPM: меньше пропускай опыт на линии, не умирай перед важными волнами и забирай безопасные руны/тома/объекты."
    if metric == "last_hits_per_min":
        return "Ластхиты: потренируй первые 10 минут и следи, чтобы каждое перемещение окупалось объектом или убийством."
    if metric == "avg_kda":
        return "KDA: перед дракой проверяй вижен, байбеки и позицию союзников; не начинай размен, где твоя смерть ничего не даёт."
    if metric == "avg_deaths":
        return "Смерти: разбери 3 последние смерти в каждой игре — без вижена, жадность, плохой TP или поздний отход."
    if metric == "hero_damage_per_min":
        return "Урон героям: ищи окна силы после ключевого предмета/уровня, но не разменивайся до покупки важных ресурсов."
    if metric == "tower_damage_per_min":
        return "Объекты: после выигранной драки сразу забирай вышку/Рошана/линию, а не просто возвращайся фармить лес."
    if metric == "teamfight_participation":
        return "Драки: заранее играй вокруг следующей цели команды, чтобы не приходить на файт на 5-10 секунд позже."
    if metric == "wards_per_match":
        return "Вардинг: ставь вижен под цель: руна/Рошан/треугольник/смок, а не просто в случайную точку."
    if metric == "camps_stacked_per_match":
        return "Стаки: делай стаки на 1:53/2:53/3:53, особенно когда линия уже запушена или кору нужен быстрый слот."
    return f"{METRIC_LABELS.get(metric, metric)}: удели этой метрике внимание в следующих играх."
