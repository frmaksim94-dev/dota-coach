"""AI analysis layer.

If Ollama is installed and the model is available, the app asks the local LLM for
a detailed coaching report. If not, a deterministic rule-based report is shown
so the app remains usable on a clean machine.
"""

from __future__ import annotations

from typing import Any

from config import OLLAMA_MODEL, USE_OLLAMA
from pro_players import generate_focus_plan, style_matches

try:  # Ollama is optional at runtime.
    from ollama import chat as ollama_chat
except Exception:  # pragma: no cover - depends on user's machine
    ollama_chat = None



def ollama_available() -> bool:
    return bool(USE_OLLAMA and ollama_chat is not None)


def analyze(text: str, model: str = OLLAMA_MODEL) -> str:
    if USE_OLLAMA and ollama_chat is not None:
        try:
            response = ollama_chat(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты русскоязычный тренер по Dota 2. Пиши конкретно, "
                            "без воды, с практическими действиями на следующие 5 игр. "
                            "Не обещай скрытую информацию и не советуй нарушать правила игры."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
            )
            return response["message"]["content"].strip()
        except Exception as exc:
            return (
                "Локальная модель Ollama сейчас недоступна, поэтому ниже показан "
                "автоматический анализ по метрикам.\n\n"
                f"Причина: {exc}\n\n"
                + text
            )
    return text


def build_prompt(
    summary: Any,
    role_info: dict[str, Any],
    comparison: list[dict[str, Any]],
    styles: list[dict[str, Any]] | None = None,
    focus_plan: list[str] | None = None,
) -> str:
    metrics = summary.metrics if hasattr(summary, "metrics") else summary.get("metrics", {})
    top_heroes = summary.top_heroes if hasattr(summary, "top_heroes") else summary.get("top_heroes", [])
    role = role_info.get("role", "Unknown")
    role_ru = role_info.get("role_ru", role)
    styles = styles if styles is not None else style_matches(metrics, role)
    focus_plan = focus_plan if focus_plan is not None else generate_focus_plan(comparison, role)

    heroes_text = "\n".join(
        f"- {h.get('name')}: {h.get('games')} игр, WR {h.get('winrate')}%, роли героя: {', '.join(h.get('roles') or [])}"
        for h in top_heroes[:8]
    ) or "Нет данных по героям."

    comparison_text = "\n".join(
        f"- {row['label']}: игрок {row['player']} / ориентир {row['target']} -> {row['status']} ({row['advice']})"
        for row in comparison
    ) or "Нет подробных метрик для сравнения."

    styles_text = "\n".join(
        f"- {s['name']}: совпадение {s['similarity']}%, стиль: {s['style']}"
        for s in styles
    ) or "Нет стилевых совпадений."

    plan_text = "\n".join(f"- {item}" for item in focus_plan) or "Нет плана."

    return f"""
Разбор игрока Dota 2.

Определенная роль: {role_ru}
Уверенность определения роли: {role_info.get('confidence', 0)}%
Причины определения роли:
{_bullet(role_info.get('reasons') or [])}

Общие метрики:
- Матчи в выборке: {metrics.get('matches', 0)}
- Winrate: {metrics.get('winrate', 0)}%
- K/D/A: {metrics.get('avg_kills', 0)} / {metrics.get('avg_deaths', 0)} / {metrics.get('avg_assists', 0)}
- KDA ratio: {metrics.get('avg_kda', 0)}
- GPM/XPM: {metrics.get('avg_gpm', 0)} / {metrics.get('avg_xpm', 0)}
- LH/min: {metrics.get('last_hits_per_min', 0)}
- Урон героям/мин: {metrics.get('hero_damage_per_min', 0)}
- Урон вышкам/мин: {metrics.get('tower_damage_per_min', 0)}
- Варды/матч: {metrics.get('wards_per_match', 0)}
- Стаки/матч: {metrics.get('camps_stacked_per_match', 0)}
- Участие в драках: {metrics.get('teamfight_participation', 0)}%

Любимые герои:
{heroes_text}

Сравнение с ориентиром роли:
{comparison_text}

Ближайшие pro-style референсы по стилю:
{styles_text}

План фокуса, который уже рассчитало приложение:
{plan_text}

Сделай финальный тренерский отчет на русском:
1. краткий диагноз игрока;
2. сильные стороны;
3. слабые стороны;
4. сравнение со стилем про-игроков этой роли;
5. конкретный план на следующие 5 игр;
6. какие 3 показателя отслеживать после каждой игры.
""".strip()


def build_rule_based_report(
    summary: Any,
    role_info: dict[str, Any],
    comparison: list[dict[str, Any]],
    styles: list[dict[str, Any]],
    focus_plan: list[str],
) -> str:
    metrics = summary.metrics if hasattr(summary, "metrics") else summary.get("metrics", {})
    role = role_info.get("role_ru", role_info.get("role", "роль не определена"))
    strengths = [row for row in comparison if row["status"] in {"сильнее ориентира", "около ориентира"}]
    weaknesses = [row for row in comparison if row["status"] in {"проседает", "сильно ниже"}]

    lines = [
        "# AI-разбор по последним играм",
        "",
        f"**Роль:** {role}  ",
        f"**Уверенность:** {role_info.get('confidence', 0)}%  ",
        f"**Выборка:** {int(metrics.get('matches', 0))} матчей, WR {metrics.get('winrate', 0)}%",
        "",
        "## Диагноз",
        (
            f"Твой профиль сейчас больше всего похож на {role}. "
            f"Средний KDA: {metrics.get('avg_kda', 0)}, GPM/XPM: "
            f"{metrics.get('avg_gpm', 0)}/{metrics.get('avg_xpm', 0)}."
        ),
        "",
        "## Сильные стороны",
    ]
    if strengths:
        lines.extend(f"- {row['label']}: {row['player']} — {row['status']}." for row in strengths[:4])
    else:
        lines.append("- Явных сильных метрик в выборке мало — лучше начать с базовой стабильности.")

    lines.extend(["", "## Что проседает"])
    if weaknesses:
        lines.extend(f"- {row['label']}: {row['player']} при ориентире {row['target']}. {row['advice']}" for row in weaknesses[:5])
    else:
        lines.append("- Критических просадок по доступным метрикам нет. Дальше нужен разбор конкретных реплеев.")

    lines.extend(["", "## На кого похож стиль"])
    if styles:
        lines.extend(f"- {s['name']} — {s['similarity']}%: {s['style']}." for s in styles)
    else:
        lines.append("- Недостаточно данных для стилевого сравнения.")

    lines.extend(["", "## План на следующие 5 игр"])
    lines.extend(f"{i}. {item}" for i, item in enumerate(focus_plan[:5], start=1))

    lines.extend(
        [
            "",
            "## Отслеживай после каждой игры",
            "- Смерти: сколько из них были без вижена или без размена.",
            "- Темп: GPM/XPM или варды/стаки, в зависимости от роли.",
            "- Объекты после выигранной драки: вышка, Рошан, линия или глубокий вижен.",
        ]
    )
    return "\n".join(lines)


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- Нет причин: мало данных."
