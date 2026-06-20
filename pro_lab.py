"""Guide and pro-pattern helpers for the Pro Lab tab.

The module deliberately uses public match/stat endpoints and local diagrams. It
creates learning cards and replay/download helpers without scraping video sites.
"""

from __future__ import annotations

import bz2
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from app_paths import resource_path, user_data_dir
from map_assets import guide_image_path
from config import REQUEST_TIMEOUT
from dota_api import OpenDotaClient, steam64_to_account_id
from role_detector import ROLE_RU


@dataclass(slots=True)
class GuidePattern:
    title: str
    role: str
    image: str
    bullets: list[str]
    drill: str


def static_patterns() -> list[GuidePattern]:
    """Built-in diagrams that explain map movement patterns."""
    return [
        GuidePattern(
            title="Керри: волна -> ближайший лес -> треугольник",
            role="Carry",
            image=str(guide_image_path("carry_farm_pattern.png")),
            bullets=[
                "Сначала забирай пачку крипов, потом только ближайший лагерь.",
                "Не переходи через темную реку без вижена и информации о вражеских героях.",
                "После ключевого предмета меняй безопасный фарм на давление вышек.",
            ],
            drill="Тренировка: 10 минут подряд считай маршрут заранее: волна, лагерь, волна, телепорт только под объект.",
        ),
        GuidePattern(
            title="Мид: руны, боковая линия, возврат в центр",
            role="Mid",
            image=str(guide_image_path("mid_rune_rotation.png")),
            bullets=[
                "Четные минуты: руна важнее лишнего удара по герою на линии.",
                "Ганк имеет смысл, если после него ты возвращаешься к пачке или объекту.",
                "Если руна плохая, пушь волну и забирай маленький лагерь/стаки.",
            ],
            drill="Тренировка: после каждой руны называй вслух следующий ресурс: пачка, лагерь, вышка или TP на сайд.",
        ),
        GuidePattern(
            title="Саппорт: вижен до драки, не после драки",
            role="Support",
            image=str(guide_image_path("support_vision_pattern.png")),
            bullets=[
                "Вард ставится перед смоком/Рошаном, а не когда команда уже дерется.",
                "Сентри сначала закрывает подходы к цели, потом глубокие точки.",
                "После выигранной драки обнови вижен на следующей зоне фарма кора.",
            ],
            drill="Тренировка: перед каждым смоком проверь две вещи: где ваш сильный кор и какой объект будет после килла.",
        ),
        GuidePattern(
            title="Оффлейн: занять опасную линию и выйти живым",
            role="Offlane",
            image=str(guide_image_path("offlane_pressure_pattern.png")),
            bullets=[
                "Твоя ценность — занять опасную линию и вынудить врага реагировать.",
                "После пуша не стой на месте: уходи в лес, за руну, к порталу или под вижен.",
                "Инициируй, когда союзники рядом; не начинай файт за экран от команды.",
            ],
            drill="Тренировка: после каждой отпушенной волны сразу нажимай на миникарту и выбирай путь отхода.",
        ),
    ]


def build_learning_feed(client: OpenDotaClient, steam64: str, role: str, limit: int = 8) -> dict[str, Any]:
    """Fetch public pro matches and build a compact learning feed."""
    account_id = steam64_to_account_id(steam64)
    heroes_by_id = client.get_heroes()
    recent = client.get_recent_matches(account_id, limit=5)
    pro_matches = client.get_pro_matches(limit=limit)

    user_match: dict[str, Any] | None = None
    if recent:
        try:
            user_match = client.get_match_details(int(recent[0].get("match_id") or 0))
        except Exception:
            user_match = dict(recent[0])

    pro_cards: list[dict[str, Any]] = []
    detailed_pro: dict[str, Any] | None = None
    for raw in pro_matches[:limit]:
        card = _pro_card_from_raw(raw, heroes_by_id)
        try:
            details = client.get_match_details(int(raw.get("match_id") or 0))
            card.update(_pro_card_from_details(details, heroes_by_id))
            if detailed_pro is None:
                detailed_pro = details
        except Exception as exc:
            card["moment"] = f"Детали матча пока недоступны: {exc}"
        pro_cards.append(card)

    comparison = build_moment_comparison(user_match, detailed_pro, account_id, role, heroes_by_id)
    return {
        "role": role,
        "role_ru": ROLE_RU.get(role, role),
        "pro_cards": pro_cards,
        "comparison": comparison,
        "user_match_id": str((user_match or {}).get("match_id") or (recent[0].get("match_id") if recent else "")),
        "pro_match_id": str((detailed_pro or {}).get("match_id") or (pro_matches[0].get("match_id") if pro_matches else "")),
    }


def _pro_card_from_raw(match: dict[str, Any], heroes_by_id: dict[int, dict[str, Any]]) -> dict[str, Any]:
    hero_name = _hero_name(match.get("hero_id"), heroes_by_id)
    start = _format_date(match.get("start_time"))
    league = match.get("league_name") or f"League {match.get('leagueid') or '—'}"
    return {
        "match_id": str(match.get("match_id") or ""),
        "league": league,
        "hero": hero_name,
        "start": start,
        "duration": _format_duration(match.get("duration")),
        "moment": "Жду подробности матча для таймкодов.",
        "lesson": "Сравни первые 10 минут: пачки, руны, TP и момент первого объекта.",
    }


def _pro_card_from_details(details: dict[str, Any], heroes_by_id: dict[int, dict[str, Any]]) -> dict[str, Any]:
    duration = _format_duration(details.get("duration"))
    objectives = details.get("objectives") or []
    teamfights = details.get("teamfights") or []
    players = details.get("players") or []
    best_player = _best_economy_player(players, heroes_by_id)
    objective_text = _first_objective_text(objectives)
    fight_text = _first_teamfight_text(teamfights)
    return {
        "duration": duration,
        "hero": best_player.get("hero", "—"),
        "moment": objective_text or fight_text or "Смотри первые 10 минут: линия -> лес -> объект без лишних смертей.",
        "lesson": best_player.get("lesson", "Отслеживай, как pro игрок превращает фарм в объект, а не просто копит золото."),
    }


def build_moment_comparison(
    user_match: dict[str, Any] | None,
    pro_match: dict[str, Any] | None,
    account_id: int,
    role: str,
    heroes_by_id: dict[int, dict[str, Any]],
) -> str:
    if not user_match and not pro_match:
        return "Пока нет матчей для сравнения. Нажми «Обновить Pro Lab», когда загрузится профиль."

    user_player = _find_user_player(user_match or {}, account_id)
    pro_player = _best_economy_player((pro_match or {}).get("players") or [], heroes_by_id, raw=True)

    lines = [f"Роль для сравнения: {ROLE_RU.get(role, role)}", ""]
    if user_match:
        lines.append(f"Твой матч: {user_match.get('match_id', '—')} | { _format_duration(user_match.get('duration')) }")
    if user_player:
        lines.extend(_player_metric_lines("Ты", user_player, heroes_by_id))
    else:
        lines.append("Твой игрок в деталях матча не найден — возможно профиль приватный или OpenDota не успел разобрать матч.")

    lines.append("")
    if pro_match:
        lines.append(f"Pro матч: {pro_match.get('match_id', '—')} | { _format_duration(pro_match.get('duration')) }")
    if pro_player:
        lines.extend(_player_metric_lines("Pro", pro_player, heroes_by_id))

    lines.extend([
        "",
        "Что смотреть в replay/demo:",
        "• 00:00-10:00 — где теряются крипы, руны, пуллы, стаки и TP.",
        "• 10:00-20:00 — была ли цель после первого сильного предмета: вышка, Рошан, глубокий вижен.",
        "• Перед смертью — был ли вижен, buyback, позиция союзников и путь отхода.",
    ])
    return "\n".join(lines)


def replay_url_from_match(match: dict[str, Any]) -> str | None:
    direct = match.get("replay_url")
    if isinstance(direct, str) and direct.startswith(("http://", "https://")):
        return direct
    cluster = match.get("cluster")
    salt = match.get("replay_salt")
    match_id = match.get("match_id")
    if cluster and salt and match_id:
        return f"http://replay{cluster}.valve.net/570/{match_id}_{salt}.dem.bz2"
    return None


def download_replay(client: OpenDotaClient, match_id: str | int, label: str = "match") -> tuple[bool, str]:
    details = client.get_match_details(int(match_id))
    url = replay_url_from_match(details)
    if not url:
        return False, "Для этого матча OpenDota не отдал replay_url/replay_salt. Попробуй другой матч или дождись разбора replay."
    target_dir = user_data_dir() / "replays"
    target_dir.mkdir(parents=True, exist_ok=True)
    raw_path = target_dir / f"{label}_{match_id}.dem.bz2"
    dem_path = target_dir / f"{label}_{match_id}.dem"
    try:
        with requests.get(url, timeout=max(REQUEST_TIMEOUT, 20), stream=True) as response:
            if not response.ok:
                return False, f"Replay не скачался: HTTP {response.status_code}"
            with raw_path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        fh.write(chunk)
    except requests.RequestException as exc:
        return False, f"Не удалось скачать replay: {exc}"

    try:
        dem_path.write_bytes(bz2.decompress(raw_path.read_bytes()))
        return True, f"Демка скачана и распакована:\n{dem_path}\n\nОткрой её через Dota 2/replay tools."
    except OSError as exc:
        return True, f"Демка скачана в сжатом виде:\n{raw_path}\n\nРаспаковка не удалась: {exc}"
    except Exception:
        return True, f"Демка скачана:\n{raw_path}\n\nФайл можно распаковать любым bz2-архиватором."


def replays_dir() -> Path:
    path = user_data_dir() / "replays"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _find_user_player(details: dict[str, Any], account_id: int) -> dict[str, Any] | None:
    for player in details.get("players") or []:
        if player.get("account_id") == account_id:
            return player
    return None


def _player_metric_lines(prefix: str, player: dict[str, Any], heroes_by_id: dict[int, dict[str, Any]]) -> list[str]:
    duration_min = max(1.0, float(player.get("duration") or 0) / 60.0)
    hero = _hero_name(player.get("hero_id"), heroes_by_id)
    gpm = _to_int(player.get("gold_per_min")) or 0
    xpm = _to_int(player.get("xp_per_min")) or 0
    lh = _to_int(player.get("last_hits")) or 0
    deaths = _to_int(player.get("deaths")) or 0
    tower = _to_int(player.get("tower_damage")) or 0
    return [
        f"{prefix}: {hero}",
        f"• GPM/XPM: {gpm}/{xpm}",
        f"• LH/min: {round(lh / duration_min, 2)} | deaths: {deaths} | tower damage: {tower}",
    ]


def _best_economy_player(players: list[dict[str, Any]], heroes_by_id: dict[int, dict[str, Any]], raw: bool = False) -> dict[str, Any]:
    if not players:
        return {} if raw else {"hero": "—", "lesson": "Нет деталей игроков."}
    sorted_players = sorted(
        players,
        key=lambda p: (_to_int(p.get("gold_per_min")) or 0) + (_to_int(p.get("xp_per_min")) or 0) + (_to_int(p.get("tower_damage")) or 0) / 20,
        reverse=True,
    )
    best = sorted_players[0]
    if raw:
        return best
    hero = _hero_name(best.get("hero_id"), heroes_by_id)
    gpm = _to_int(best.get("gold_per_min")) or 0
    xpm = _to_int(best.get("xp_per_min")) or 0
    tower = _to_int(best.get("tower_damage")) or 0
    return {
        "hero": hero,
        "lesson": f"Фокус: {hero} держит темп {gpm}/{xpm} GPM/XPM и переводит ресурсы в {tower} tower damage.",
    }


def _first_objective_text(objectives: list[dict[str, Any]]) -> str:
    for obj in objectives:
        subtype = str(obj.get("subtype") or obj.get("type") or "objective")
        time_sec = _to_int(obj.get("time")) or 0
        if time_sec >= 0:
            return f"Таймкод {_format_clock(time_sec)}: первый важный объект — {subtype}. Смотри, какая волна/вижен подготовили этот момент."
    return ""


def _first_teamfight_text(teamfights: list[dict[str, Any]]) -> str:
    for fight in teamfights:
        start = _to_int(fight.get("start")) or _to_int(fight.get("start_time")) or 0
        end = _to_int(fight.get("end")) or start + 45
        if start >= 0:
            return f"Таймкод {_format_clock(start)}-{_format_clock(end)}: первая драка. Сравни позицию коров и саппортов до начала файта."
    return ""


def _hero_name(hero_id: Any, heroes_by_id: dict[int, dict[str, Any]]) -> str:
    try:
        hero = heroes_by_id.get(int(hero_id)) or {}
    except (TypeError, ValueError):
        hero = {}
    return hero.get("localized_name") or f"Hero {hero_id or '—'}"


def _format_date(ts: Any) -> str:
    value = _to_int(ts)
    if not value:
        return "—"
    return time.strftime("%d.%m.%Y", time.localtime(value))


def _format_duration(seconds: Any) -> str:
    value = _to_int(seconds) or 0
    if value <= 0:
        return "—"
    return f"{value // 60}:{value % 60:02d}"


def _format_clock(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None
