"""Application settings for Dota Coach AI.

Most values can be overridden through environment variables so the project can be
shared without hard-coding personal tokens.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Dota Coach AI"
APP_VERSION = "0.9.6"

# Default account is empty so the app can be shared. Enter Steam64/account_id in the UI
# or override it before launch: set DOTA_STEAM64=7656...
STEAM64 = int(os.getenv("DOTA_STEAM64", "0") or "0")

OPENDOTA_API_URL = os.getenv("OPENDOTA_API_URL", "https://api.opendota.com/api").rstrip("/")
OPENDOTA_API_KEY = os.getenv("OPENDOTA_API_KEY", "").strip()
REQUEST_TIMEOUT = float(os.getenv("DOTA_COACH_TIMEOUT", "12"))
CACHE_DIR = Path(os.getenv("DOTA_COACH_CACHE", Path.home() / ".dota_coach_ai" / "cache"))
CACHE_TTL_SECONDS = int(os.getenv("DOTA_COACH_CACHE_TTL", "300"))
MAX_RECENT_MATCH_DETAILS = int(os.getenv("DOTA_COACH_MATCH_DETAILS", "8"))

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", os.getenv("DOTA_COACH_MODEL", "qwen3:8b"))
USE_OLLAMA = os.getenv("DOTA_COACH_USE_OLLAMA", "1").strip().lower() not in {"0", "false", "no", "off"}

# Game State Integration: Dota sends HTTP POST requests to this local endpoint
# when a gamestate_integration_*.cfg file is installed in the Dota cfg folder.
GSI_HOST = os.getenv("DOTA_COACH_GSI_HOST", "127.0.0.1")
GSI_PORT = int(os.getenv("DOTA_COACH_GSI_PORT", "3000"))
GSI_AUTH_TOKEN = os.getenv("DOTA_COACH_GSI_TOKEN", "dota_coach_ai")
