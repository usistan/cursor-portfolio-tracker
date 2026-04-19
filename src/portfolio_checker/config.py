from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _clean_credential(raw: str) -> str:
    """Entfernt BOM, äußere Whitespaces und einfache Anführungszeichen aus .env-Zeilen."""
    s = raw.strip().lstrip("\ufeff")
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    return s.strip()


@dataclass(frozen=True)
class EtradeSettings:
    consumer_key: str
    consumer_secret: str
    sandbox: bool
    token_path: Path


def load_etrade_settings() -> EtradeSettings:
    """Lädt E*TRADE-Credentials aus der Umgebung (.env optional)."""
    load_dotenv()
    key = _clean_credential(os.environ.get("ETRADE_CONSUMER_KEY", ""))
    secret = _clean_credential(os.environ.get("ETRADE_CONSUMER_SECRET", ""))
    if not key or not secret:
        raise RuntimeError(
            "ETRADE_CONSUMER_KEY und ETRADE_CONSUMER_SECRET müssen gesetzt sein "
            "(z. B. via env.example kopieren nach .env)."
        )
    # Default: Produktion — wer Sandbox will, setzt ETRADE_SANDBOX=true
    sandbox = os.environ.get("ETRADE_SANDBOX", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    raw_path = os.environ.get("ETRADE_TOKEN_PATH", ".etrade_tokens.json").strip()
    token_path = Path(raw_path).expanduser()
    return EtradeSettings(
        consumer_key=key,
        consumer_secret=secret,
        sandbox=sandbox,
        token_path=token_path,
    )


@dataclass(frozen=True)
class SchwabSettings:
    api_key: str
    app_secret: str
    callback_url: str
    token_path: Path


def load_schwab_settings() -> SchwabSettings:
    """Charles Schwab Trader API (OAuth 2.0) — siehe env.example."""
    load_dotenv()
    api_key = _clean_credential(os.environ.get("SCHWAB_API_KEY", ""))
    secret = _clean_credential(os.environ.get("SCHWAB_APP_SECRET", ""))
    if not api_key or not secret:
        raise RuntimeError(
            "SCHWAB_API_KEY und SCHWAB_APP_SECRET müssen gesetzt sein "
            "(Registrierung: https://developer.schwab.com/)."
        )
    callback = _clean_credential(
        os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182")
    )
    raw_path = os.environ.get("SCHWAB_TOKEN_PATH", ".schwab_token.json").strip()
    return SchwabSettings(
        api_key=api_key,
        app_secret=secret,
        callback_url=callback,
        token_path=Path(raw_path).expanduser(),
    )
