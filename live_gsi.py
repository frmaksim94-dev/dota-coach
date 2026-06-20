"""Dota 2 Game State Integration receiver.

This module creates a tiny local HTTP server. When Dota's GSI config points to
it, the game posts JSON snapshots that the UI can turn into safe coaching tips.
It does not read game memory, does not inspect the screen, and does not expose
hidden information from fog of war.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import requests

from config import GSI_AUTH_TOKEN, GSI_HOST, GSI_PORT, REQUEST_TIMEOUT

SnapshotCallback = Callable[[dict[str, Any]], None]


class GSIReceiver:
    def __init__(self, host: str = GSI_HOST, port: int = GSI_PORT, auth_token: str = GSI_AUTH_TOKEN) -> None:
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._latest: dict[str, Any] = {}
        self._last_seen = 0.0
        self._request_count = 0
        self._last_path = ""
        self._last_error = ""
        self._lock = threading.Lock()
        self._callbacks: list[SnapshotCallback] = []
        self._bound_host = ""

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def endpoint(self) -> str:
        # Dota accepts an HTTP URI; keeping the trailing slash matches common
        # GSI examples and avoids users comparing two slightly different URIs.
        return f"http://{self.host}:{self.port}/"

    @property
    def request_count(self) -> int:
        with self._lock:
            return self._request_count

    @property
    def last_path(self) -> str:
        with self._lock:
            return self._last_path

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    def add_callback(self, callback: SnapshotCallback) -> None:
        self._callbacks.append(callback)

    def start(self) -> None:
        if self._server is not None:
            return

        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                # A tiny health endpoint makes it easier to diagnose whether the
                # local server is actually listening on 127.0.0.1:3000.
                if self.path.rstrip("/") in {"", "/health"}:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true,"service":"DotaCoachAI GSI"}')
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8")) if raw else {}
                except json.JSONDecodeError:
                    receiver._mark_error(self.path, "invalid json")
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"invalid json")
                    return

                if receiver.auth_token:
                    token = str((payload.get("auth") or {}).get("token", ""))
                    # Some Dota builds omit auth if the cfg is edited by hand.
                    # Accept an empty token, but reject an explicit wrong token.
                    if token and token != receiver.auth_token:
                        receiver._mark_error(self.path, "bad token")
                        self.send_response(403)
                        self.end_headers()
                        self.wfile.write(b"bad token")
                        return

                receiver._update(payload, self.path)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, format: str, *args: Any) -> None:  # keep UI console clean
                return

        try:
            self._server = ThreadingHTTPServer((self.host, self.port), Handler)
            self._bound_host = self.host
        except OSError:
            # On some Windows systems another local policy blocks binding exactly
            # to 127.0.0.1 but allows listening on all interfaces. The cfg still
            # points Dota to 127.0.0.1; binding 0.0.0.0 also accepts that traffic.
            if self.host not in {"0.0.0.0", ""}:
                self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
                self._bound_host = "0.0.0.0"
            else:
                raise
        self._thread = threading.Thread(target=self._server.serve_forever, name="DotaCoachGSI", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        server = self._server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        self._server = None
        self._thread = None

    def latest(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest)

    def seconds_since_last_snapshot(self) -> float | None:
        with self._lock:
            if not self._last_seen:
                return None
            return time.time() - self._last_seen

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            seconds = None if not self._last_seen else time.time() - self._last_seen
            return {
                "running": self.is_running,
                "endpoint": self.endpoint,
                "bound_host": self._bound_host,
                "request_count": self._request_count,
                "last_seen_seconds": seconds,
                "last_path": self._last_path,
                "last_error": self._last_error,
                "has_payload": bool(self._latest),
            }

    def _mark_error(self, path: str, message: str) -> None:
        with self._lock:
            self._last_path = path
            self._last_error = message

    def _update(self, payload: dict[str, Any], path: str = "/") -> None:
        with self._lock:
            self._latest = payload
            self._last_seen = time.time()
            self._request_count += 1
            self._last_path = path
            self._last_error = ""
        for callback in list(self._callbacks):
            try:
                callback(payload)
            except Exception:
                pass


class LiveCoach:
    def __init__(self, role: str = "Carry") -> None:
        self.role = role

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider = payload.get("provider") or {}
        map_data = payload.get("map") or {}
        player = payload.get("player") or {}
        hero = payload.get("hero") or {}
        items = payload.get("items") or {}

        clock = _to_int(map_data.get("clock_time"))
        minute = round(clock / 60, 1) if clock is not None and clock >= 0 else 0.0
        hero_name = _clean_hero_name(hero.get("name") or player.get("hero_name") or "unknown")
        health = _to_float(hero.get("health"))
        max_health = _to_float(hero.get("max_health"))
        mana = _to_float(hero.get("mana"))
        max_mana = _to_float(hero.get("max_mana"))
        alive = hero.get("alive")
        if isinstance(alive, str):
            alive = alive.lower() not in {"false", "0", "dead"}

        gold = _to_int(player.get("gold"))
        if gold is None:
            gold = (_to_int(player.get("gold_reliable")) or 0) + (_to_int(player.get("gold_unreliable")) or 0)
        last_hits = _to_int(player.get("last_hits")) or _to_int(hero.get("last_hits")) or 0
        denies = _to_int(player.get("denies")) or 0
        kills = _to_int(player.get("kills")) or 0
        deaths = _to_int(player.get("deaths")) or 0
        assists = _to_int(player.get("assists")) or 0
        gpm = _to_int(player.get("gpm")) or _to_int(player.get("gold_per_min"))
        xpm = _to_int(player.get("xpm")) or _to_int(player.get("xp_per_min"))

        return {
            "provider": provider.get("name", "Dota 2"),
            "map": map_data.get("name", "unknown"),
            "game_state": map_data.get("game_state", map_data.get("match_state", "unknown")),
            "clock_time": clock,
            "minute": minute,
            "hero": hero_name,
            "level": _to_int(hero.get("level")) or 0,
            "alive": alive if alive is not None else True,
            "respawn_seconds": _to_int(hero.get("respawn_seconds")) or 0,
            "health_ratio": _ratio(health, max_health),
            "mana_ratio": _ratio(mana, max_mana),
            "gold": gold or 0,
            "last_hits": last_hits,
            "denies": denies,
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "gpm": gpm or 0,
            "xpm": xpm or 0,
            "items": _extract_item_names(items),
        }

    def tip(self, payload: dict[str, Any]) -> str:
        if not payload:
            return "Жду данные от Dota 2. Запусти GSI и матч, затем проверь, что cfg установлен в папку игры."
        s = self.summarize(payload)
        tips: list[str] = []
        minute = float(s["minute"] or 0)
        role = self.role

        if s["alive"] is False:
            respawn = int(s.get("respawn_seconds") or 0)
            tips.append(f"Ты мертв. За {respawn} сек. проверь байбек, следующий объект и что купить после респавна.")
        if s["health_ratio"] and s["health_ratio"] < 0.28 and s["alive"]:
            tips.append("Мало HP: не стой без вижена, отойди к безопасной линии/саппорту или донеси реген.")
        if s["mana_ratio"] and s["mana_ratio"] < 0.18 and role in {"Mid", "Soft Support", "Hard Support"}:
            tips.append("Мало маны: следующий файт может быть слабым. Подумай о руне, базе, манго/clarity или игре от кулдаунов.")
        if s["gold"] >= 2200:
            tips.append("Много неиспользованного золота: купи ключевой компонент до драки, чтобы не умереть с голдой в инвентаре.")

        if minute <= 10:
            tips.extend(self._early_game_tips(s, role, minute))
        elif minute <= 25:
            tips.extend(self._mid_game_tips(s, role))
        else:
            tips.extend(self._late_game_tips(s, role))

        if not tips:
            tips.append("Состояние нормальное. Следующее решение: линия -> вижен -> объект, а не случайный фарм без цели.")
        return "\n".join(f"• {tip}" for tip in tips[:4])

    def _early_game_tips(self, s: dict[str, Any], role: str, minute: float) -> list[str]:
        tips: list[str] = []
        lh = int(s["last_hits"] or 0)
        if role == "Carry":
            target = int(max(1, minute) * 6.0)
            if minute >= 4 and lh < target * 0.75:
                tips.append(f"Ластхиты ниже темпа керри: {lh}/{target}. Не уходи с линии без руны/килла/стака.")
            else:
                tips.append("Керри-фокус: добивай пачку, затем ближайший лагерь; не принимай драку без сильного спелла саппорта.")
        elif role == "Mid":
            target = int(max(1, minute) * 5.2)
            if minute >= 4 and lh < target * 0.75:
                tips.append(f"Мид-темп по крипам проседает: {lh}/{target}. Проверь блок крипов, агр и контроль рун.")
            tips.append("Мид-фокус: контролируй руны на четных минутах и сообщай команде о первом сильном тайминге.")
        elif role == "Offlane":
            tips.append("Оффлейн-фокус: забери опыт, сломай комфорт керри и не отдай смерть без размена ресурсов.")
        else:
            tips.append("Саппорт-фокус: проверь пулл/стак, вижен под руну и TP на спасение кора.")
        return tips

    def _mid_game_tips(self, s: dict[str, Any], role: str) -> list[str]:
        if role in {"Carry", "Mid"}:
            return ["Мидгейм: играй от следующего предмета. Если слот близко, не дерись до покупки; если слот готов — зови на объект."]
        if role == "Offlane":
            return ["Мидгейм оффлейна: твоя задача — начать хороший файт или занять опасную линию, пока керри фармит безопасно."]
        return ["Мидгейм саппорта: поставь вижен до смока, а не после. Играй вокруг сильнейшего кора и ближайшей цели."]

    def _late_game_tips(self, s: dict[str, Any], role: str) -> list[str]:
        if role in {"Carry", "Mid"}:
            return ["Лейт: не показывайся первым на линии без байбека/вижена. После килла сразу думай про Рошана или high ground."]
        return ["Лейт: твоя смерть может стоить игры. Держи buyback, вижен вокруг Рошана и сейв-позицию за кором."]


def make_gsi_config_text(endpoint: str | None = None, token: str = GSI_AUTH_TOKEN) -> str:
    endpoint = endpoint or f"http://{GSI_HOST}:{GSI_PORT}/"
    if not endpoint.endswith("/"):
        endpoint += "/"
    # Dota is tolerant to the block name in many setups, but this sample name is
    # closest to common Dota GSI examples and avoids configs being silently ignored.
    return f'''"dota2-gsi Configuration"
{{
    "uri"           "{endpoint}"
    "timeout"       "5.0"
    "buffer"        "0.1"
    "throttle"      "0.25"
    "heartbeat"     "5.0"
    "auth"
    {{
        "token"     "{token}"
    }}
    "data"
    {{
        "provider"      "1"
        "map"           "1"
        "player"        "1"
        "hero"          "1"
        "abilities"     "1"
        "items"         "1"
        "buildings"     "1"
        "draft"         "1"
        "wearables"     "1"
    }}
}}
'''


def write_gsi_config(path: str | Path, endpoint: str | None = None, token: str = GSI_AUTH_TOKEN) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(make_gsi_config_text(endpoint=endpoint, token=token), encoding="utf-8")
    return file_path


def local_probe(endpoint: str | None = None, token: str = GSI_AUTH_TOKEN) -> tuple[bool, str]:
    """Post a tiny fake Dota snapshot to the local GSI endpoint.

    This does not test whether Dota 2 is configured correctly. It tests the app's
    local HTTP server. If it passes but Dota still says no data, the problem is
    almost always the cfg location, launch option, or Dota not being restarted.
    """
    endpoint = endpoint or f"http://{GSI_HOST}:{GSI_PORT}/"
    if not endpoint.endswith("/"):
        endpoint += "/"
    payload = {
        "auth": {"token": token},
        "provider": {"name": "Dota 2", "appid": 570, "version": 1},
        "map": {"name": "start", "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS", "clock_time": 375},
        "player": {"gold": 721, "last_hits": 34, "denies": 5, "kills": 1, "deaths": 0, "assists": 2, "gpm": 442, "xpm": 518},
        "hero": {"name": "npc_dota_hero_juggernaut", "level": 7, "alive": True, "health": 790, "max_health": 980, "mana": 210, "max_mana": 338},
        "items": {},
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=min(REQUEST_TIMEOUT, 3.0))
    except requests.RequestException as exc:
        return False, f"Локальный тест не дошел до сервера: {exc}"
    if response.ok:
        return True, f"Локальный тест прошел: HTTP {response.status_code}. Сервер приложения принимает JSON."
    return False, f"Сервер ответил HTTP {response.status_code}: {response.text[:160]}"


def _extract_item_names(items: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for value in items.values() if isinstance(items, dict) else []:
        if isinstance(value, dict):
            name = value.get("name")
        else:
            name = value
        if isinstance(name, str) and name and name != "empty":
            result.append(name.replace("item_", ""))
    return result


def _clean_hero_name(name: str) -> str:
    if not name:
        return "unknown"
    return str(name).replace("npc_dota_hero_", "").replace("_", " ").title()


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(current: float | None, maximum: float | None) -> float:
    if current is None or not maximum:
        return 0.0
    return max(0.0, min(1.0, current / maximum))
