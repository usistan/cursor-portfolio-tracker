from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class EtradeSettings:
    consumer_key: str
    consumer_secret: str
    sandbox: bool
    token_path: Path


def load_etrade_settings() -> EtradeSettings:
    """Lädt E*TRADE-Credentials aus der Umgebung (.env optional)."""
    load_dotenv()
    key = os.environ.get("ETRADE_CONSUMER_KEY", "").strip()
    secret = os.environ.get("ETRADE_CONSUMER_SECRET", "").strip()
    if not key or not secret:
        raise RuntimeError(
            "ETRADE_CONSUMER_KEY und ETRADE_CONSUMER_SECRET müssen gesetzt sein "
            "(z. B. via env.example kopieren nach .env)."
        )
    sandbox = os.environ.get("ETRADE_SANDBOX", "true").lower() in (
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
