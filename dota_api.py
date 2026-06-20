"""OpenDota client and metric aggregation.

The app intentionally uses the public OpenDota REST API for post-match data.
Live in-game data is handled separately by live_gsi.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

from config import (
    CACHE_DIR,
    CACHE_TTL_SECONDS,
    OPENDOTA_API_KEY,
    OPENDOTA_API_URL,
    REQUEST_TIMEOUT,
    STEAM64,
    MAX_RECENT_MATCH_DETAILS,
)

STEAM64_OFFSET = 76561197960265728


class OpenDotaError(RuntimeError):
    """Raised when the OpenDota API cannot be reached or returns invalid data."""


def _extract_numeric_steam_value(value: int | str) -> int:
    """Accept Steam64, account_id, OpenDota player URL, or Steam profile URL."""
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    # https://www.opendota.com/players/123456789 -> account_id
    match = re.search(r"(?:opendota\.com/players/|players/)(\d{3,12})", text, re.I)
    if match:
        return int(match.group(1))
    # https://steamcommunity.com/profiles/7656119... -> Steam64
    match = re.search(r"steamcommunity\.com/profiles/(\d{15,20})", text, re.I)
    if match:
        return int(match.group(1))
    # Plain numeric Steam64/account_id, with spaces allowed.
    digits = re.sub(r"\D", "", text)
    if not digits:
        raise ValueError("Вставь Steam64, account_id или ссылку OpenDota/Steam profile.")
    return int(digits)


def steam64_to_account_id(steam64: int | str) -> int:
    value = _extract_numeric_steam_value(steam64)
    if value > STEAM64_OFFSET:
        return value - STEAM64_OFFSET
    # Allow the user to paste an already converted account_id.
    return value


def account_id_to_display_steam64(value: int | str) -> int:
    raw = _extract_numeric_steam_value(value)
    if raw > STEAM64_OFFSET:
        return raw
    return raw + STEAM64_OFFSET


@dataclass(slots=True)
class PlayerMatchPerformance:
    match_id: int
    hero_id: int | None = None
    duration: int = 0
    start_time: int | None = None
    win: bool = False
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    gold_per_min: int | None = None
    xp_per_min: int | None = None
    last_hits: int | None = None
    denies: int | None = None
    hero_damage: int | None = None
    tower_damage: int | None = None
    hero_healing: int | None = None
    obs_placed: int | None = None
    sen_placed: int | None = None
    camps_stacked: int | None = None
    runes_grabbed: int | None = None
    teamfight_participation: float | None = None
    lane_role: int | None = None
    is_roaming: bool | None = None
    source: str = "recent"


@dataclass(slots=True)
class PlayerSummary:
    steam64: int
    account_id: int
    total_recent_matches: int
    detailed_matches: int
    winrate: float
    metrics: dict[str, float]
    top_heroes: list[dict[str, Any]]
    recent_matches: list[dict[str, Any]]
    performances: list[dict[str, Any]]
    heroes_by_id: dict[int, dict[str, Any]]
    errors: list[str]


class OpenDotaClient:
    def __init__(self, base_url: str = OPENDOTA_API_URL, timeout: float = REQUEST_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, path: str, params: dict[str, Any] | None) -> Path:
        raw = json.dumps({"path": path, "params": params or {}}, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        return CACHE_DIR / f"{digest}.json"

    def _get(self, path: str, params: dict[str, Any] | None = None, max_age: int = CACHE_TTL_SECONDS) -> Any:
        params = dict(params or {})
        if OPENDOTA_API_KEY:
            params.setdefault("api_key", OPENDOTA_API_KEY)

        cache_file = self._cache_path(path, params)
        if cache_file.exists() and max_age > 0:
            age = time.time() - cache_file.stat().st_mtime
            if age <= max_age:
                try:
                    return json.loads(cache_file.read_text("utf-8"))
                except json.JSONDecodeError:
                    cache_file.unlink(missing_ok=True)

        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            if cache_file.exists():
                try:
                    return json.loads(cache_file.read_text("utf-8"))
                except json.JSONDecodeError:
                    pass
            raise OpenDotaError(f"Не удалось подключиться к OpenDota: {exc}") from exc

        if response.status_code == 429:
            if cache_file.exists():
                return json.loads(cache_file.read_text("utf-8"))
            raise OpenDotaError("OpenDota временно ограничил запросы. Попробуй позже или добавь OPENDOTA_API_KEY.")
        if not response.ok:
            raise OpenDotaError(f"OpenDota вернул HTTP {response.status_code}: {response.text[:200]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise OpenDotaError("OpenDota вернул не JSON-ответ.") from exc

        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def get_recent_matches(self, account_id: int, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get(f"players/{account_id}/recentMatches", max_age=180)
        if not isinstance(data, list):
            raise OpenDotaError("Некорректный ответ recentMatches.")
        return data[:limit]

    def get_player_heroes(self, account_id: int) -> list[dict[str, Any]]:
        data = self._get(f"players/{account_id}/heroes", max_age=3600)
        if not isinstance(data, list):
            return []
        return sorted(data, key=lambda row: int(row.get("games") or 0), reverse=True)

    def get_heroes(self) -> dict[int, dict[str, Any]]:
        data = self._get("heroes", max_age=24 * 3600)
        heroes: dict[int, dict[str, Any]] = {}
        if isinstance(data, list):
            for hero in data:
                try:
                    heroes[int(hero["id"])] = hero
                except (KeyError, TypeError, ValueError):
                    continue
        return heroes

    def get_match_details(self, match_id: int) -> dict[str, Any]:
        return self._get(f"matches/{match_id}", max_age=24 * 3600)

    def get_pro_matches(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent professional match rows from OpenDota.

        The endpoint is intentionally lightweight; detailed moments are fetched
        lazily only for a few matches in the Pro Lab page to avoid rate limits.
        """
        data = self._get("proMatches", max_age=15 * 60)
        if not isinstance(data, list):
            return []
        return data[: max(0, limit)]

    def get_public_hero_stats(self) -> list[dict[str, Any]]:
        """Return current public hero meta rows from OpenDota /heroStats."""
        data = self._get("heroStats", max_age=6 * 3600)
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def get_player_summary(
        self,
        steam64: int | str = STEAM64,
        recent_limit: int = 20,
        detail_limit: int = MAX_RECENT_MATCH_DETAILS,
    ) -> PlayerSummary:
        account_id = steam64_to_account_id(steam64)
        steam64_int = account_id_to_display_steam64(steam64)
        errors: list[str] = []

        recent_matches = self.get_recent_matches(account_id, recent_limit)
        hero_stats = self.get_player_heroes(account_id)
        heroes_by_id = self.get_heroes()

        performances: list[PlayerMatchPerformance] = []
        for match in recent_matches[: max(0, detail_limit)]:
            match_id = int(match.get("match_id") or 0)
            if not match_id:
                continue
            try:
                details = self.get_match_details(match_id)
                player = self._find_player_in_match(details, account_id, match)
                performances.append(self._performance_from_detail(details, player, match))
            except Exception as exc:  # keep loading even if one parsed match is unavailable
                errors.append(f"Матч {match_id}: {exc}")
                performances.append(self._performance_from_recent(match))

        if not performances:
            performances = [self._performance_from_recent(match) for match in recent_matches]

        metrics = self._build_metrics(performances)
        winrate = metrics.get("winrate", 0.0)
        top_heroes = self._build_top_heroes(hero_stats, heroes_by_id)

        return PlayerSummary(
            steam64=steam64_int,
            account_id=account_id,
            total_recent_matches=len(recent_matches),
            detailed_matches=sum(1 for p in performances if p.source == "detail"),
            winrate=winrate,
            metrics=metrics,
            top_heroes=top_heroes,
            recent_matches=recent_matches,
            performances=[asdict(p) for p in performances],
            heroes_by_id=heroes_by_id,
            errors=errors[:5],
        )

    def _find_player_in_match(
        self, details: dict[str, Any], account_id: int, recent_match: dict[str, Any]
    ) -> dict[str, Any]:
        players = details.get("players") or []
        for player in players:
            if player.get("account_id") == account_id:
                return player
        # Private profile or anonymized account: fallback to player_slot from recent match.
        recent_slot = recent_match.get("player_slot")
        for player in players:
            if player.get("player_slot") == recent_slot:
                return player
        raise OpenDotaError("игрок не найден в деталях матча")

    def _performance_from_detail(
        self, details: dict[str, Any], player: dict[str, Any], recent_match: dict[str, Any]
    ) -> PlayerMatchPerformance:
        radiant_win = bool(details.get("radiant_win", recent_match.get("radiant_win", False)))
        player_slot = int(player.get("player_slot", recent_match.get("player_slot", 0)) or 0)
        is_radiant = player_slot < 128
        return PlayerMatchPerformance(
            match_id=int(details.get("match_id") or recent_match.get("match_id") or 0),
            hero_id=_to_int(player.get("hero_id", recent_match.get("hero_id"))),
            duration=_to_int(details.get("duration", recent_match.get("duration"))) or 0,
            start_time=_to_int(details.get("start_time", recent_match.get("start_time"))),
            win=(radiant_win and is_radiant) or ((not radiant_win) and (not is_radiant)),
            kills=_to_int(player.get("kills")) or 0,
            deaths=_to_int(player.get("deaths")) or 0,
            assists=_to_int(player.get("assists")) or 0,
            gold_per_min=_to_int(player.get("gold_per_min")),
            xp_per_min=_to_int(player.get("xp_per_min")),
            last_hits=_to_int(player.get("last_hits")),
            denies=_to_int(player.get("denies")),
            hero_damage=_to_int(player.get("hero_damage")),
            tower_damage=_to_int(player.get("tower_damage")),
            hero_healing=_to_int(player.get("hero_healing")),
            obs_placed=_to_int(player.get("obs_placed")),
            sen_placed=_to_int(player.get("sen_placed")),
            camps_stacked=_to_int(player.get("camps_stacked")),
            runes_grabbed=_to_int(player.get("runes_grabbed")),
            teamfight_participation=_to_float(player.get("teamfight_participation")),
            lane_role=_to_int(player.get("lane_role")),
            is_roaming=bool(player.get("is_roaming")) if player.get("is_roaming") is not None else None,
            source="detail",
        )

    def _performance_from_recent(self, match: dict[str, Any]) -> PlayerMatchPerformance:
        radiant_win = bool(match.get("radiant_win", False))
        player_slot = int(match.get("player_slot", 0) or 0)
        is_radiant = player_slot < 128
        return PlayerMatchPerformance(
            match_id=int(match.get("match_id") or 0),
            hero_id=_to_int(match.get("hero_id")),
            duration=_to_int(match.get("duration")) or 0,
            start_time=_to_int(match.get("start_time")),
            win=(radiant_win and is_radiant) or ((not radiant_win) and (not is_radiant)),
            kills=_to_int(match.get("kills")) or 0,
            deaths=_to_int(match.get("deaths")) or 0,
            assists=_to_int(match.get("assists")) or 0,
            source="recent",
        )

    def _build_top_heroes(
        self, hero_stats: list[dict[str, Any]], heroes_by_id: dict[int, dict[str, Any]], limit: int = 12
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in hero_stats[:limit]:
            hero_id = _to_int(row.get("hero_id")) or 0
            games = _to_int(row.get("games")) or 0
            wins = _to_int(row.get("win")) or 0
            hero = heroes_by_id.get(hero_id, {})
            result.append(
                {
                    "hero_id": hero_id,
                    "name": hero.get("localized_name") or f"Hero {hero_id}",
                    "games": games,
                    "wins": wins,
                    "winrate": round(wins / games * 100, 1) if games else 0.0,
                    "roles": hero.get("roles") or [],
                }
            )
        return result

    def _build_metrics(self, performances: list[PlayerMatchPerformance]) -> dict[str, float]:
        games = len(performances)
        if games == 0:
            return {}
        wins = sum(1 for p in performances if p.win)
        duration_minutes = [_duration_minutes(p.duration) for p in performances]
        kills = [p.kills for p in performances]
        deaths = [p.deaths for p in performances]
        assists = [p.assists for p in performances]
        kda_values = [(p.kills + p.assists) / max(1, p.deaths) for p in performances]
        last_hits_per_min = [safe_div(p.last_hits, mins) for p, mins in zip(performances, duration_minutes) if p.last_hits is not None]
        tower_damage_per_min = [safe_div(p.tower_damage, mins) for p, mins in zip(performances, duration_minutes) if p.tower_damage is not None]
        hero_damage_per_min = [safe_div(p.hero_damage, mins) for p, mins in zip(performances, duration_minutes) if p.hero_damage is not None]
        wards_per_match = [float((p.obs_placed or 0) + (p.sen_placed or 0)) for p in performances if p.obs_placed is not None or p.sen_placed is not None]
        camps_stacked = [float(p.camps_stacked or 0) for p in performances if p.camps_stacked is not None]
        teamfight = [p.teamfight_participation for p in performances if p.teamfight_participation is not None]

        return {
            "matches": float(games),
            "wins": float(wins),
            "losses": float(games - wins),
            "winrate": round(wins / games * 100, 1),
            "avg_kills": round(mean(kills), 2),
            "avg_deaths": round(mean(deaths), 2),
            "avg_assists": round(mean(assists), 2),
            "avg_kda": round(mean(kda_values), 2),
            "avg_gpm": round(mean([p.gold_per_min for p in performances if p.gold_per_min is not None]), 1),
            "avg_xpm": round(mean([p.xp_per_min for p in performances if p.xp_per_min is not None]), 1),
            "last_hits_per_min": round(mean(last_hits_per_min), 2),
            "hero_damage_per_min": round(mean(hero_damage_per_min), 1),
            "tower_damage_per_min": round(mean(tower_damage_per_min), 1),
            "wards_per_match": round(mean(wards_per_match), 2),
            "camps_stacked_per_match": round(mean(camps_stacked), 2),
            "teamfight_participation": round(mean(teamfight) * 100, 1) if teamfight else 0.0,
            "avg_duration_min": round(mean(duration_minutes), 1),
        }


def get_recent_matches() -> list[dict[str, Any]]:
    client = OpenDotaClient()
    return client.get_recent_matches(steam64_to_account_id(STEAM64))


def get_winrate() -> tuple[int, float]:
    client = OpenDotaClient()
    summary = client.get_player_summary(STEAM64, detail_limit=0)
    return int(summary.metrics.get("matches", 0)), float(summary.winrate)


def get_hero_stats() -> list[dict[str, Any]]:
    client = OpenDotaClient()
    return client.get_player_heroes(steam64_to_account_id(STEAM64))


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values: list[float | int | None]) -> float:
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return 0.0
    return sum(cleaned) / len(cleaned)


def safe_div(a: int | float | None, b: int | float | None) -> float:
    if a is None or b in (None, 0):
        return 0.0
    return float(a) / float(b)


def _duration_minutes(seconds: int | None) -> float:
    if not seconds:
        return 1.0
    return max(1.0, float(seconds) / 60.0)
