from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def load_env_files() -> None:
    """
    Lädt ``.env`` aus dem aktuellen Arbeitsverzeichnis, danach aus dem
    Projektroot (neben ``pyproject.toml``), ohne bereits gesetzte Variablen
    zu überschreiben. So funktionieren CLI-Aufrufe auch außerhalb des Repos.
    """
    load_dotenv()
    project_root = Path(__file__).resolve().parents[2] / ".env"
    if project_root.is_file():
        load_dotenv(project_root, override=False)


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
    load_env_files()
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
    load_env_files()
    api_key = _clean_credential(os.environ.get("SCHWAB_API_KEY", ""))
    secret = _clean_credential(os.environ.get("SCHWAB_APP_SECRET", ""))
    if not api_key or not secret:
        raise RuntimeError(
            "SCHWAB_API_KEY und SCHWAB_APP_SECRET müssen gesetzt sein "
            "(Registrierung: https://developer.schwab.com/). "
            "CLI im Projektordner ausführen oder .env dort ablegen — "
            "siehe load_env_files() in config.py."
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


@dataclass(frozen=True)
class IbkrSettings:
    """Interactive Brokers Client Portal API (über ``ibind``)."""

    host: str
    port: int
    base_route: str
    account_id: str | None
    use_oauth: bool
    cacert: str | bool
    rest_url: str | None


def load_ibkr_settings() -> IbkrSettings:
    """Liest Gateway- oder OAuth-Einstellungen; siehe env.example."""
    load_env_files()
    use_oauth = os.environ.get("IBKR_USE_OAUTH", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    aid = _clean_credential(os.environ.get("IBKR_ACCOUNT_ID", ""))
    account_id = aid if aid else None
    host = _clean_credential(os.environ.get("IBKR_GATEWAY_HOST", "127.0.0.1"))
    try:
        port = int(os.environ.get("IBKR_GATEWAY_PORT", "5000").strip() or "5000")
    except ValueError as e:
        raise RuntimeError("IBKR_GATEWAY_PORT muss eine Zahl sein.") from e
    base = _clean_credential(os.environ.get("IBKR_BASE_ROUTE", "/v1/api/"))
    if not base.startswith("/"):
        base = "/" + base
    if not base.endswith("/"):
        base = base + "/"
    cacert_raw = os.environ.get("IBKR_CACERT", "").strip()
    cacert: str | bool = cacert_raw if cacert_raw else False
    rest_raw = _clean_credential(os.environ.get("IBKR_REST_URL", ""))
    rest_url = rest_raw if rest_raw else None
    return IbkrSettings(
        host=host,
        port=port,
        base_route=base,
        account_id=account_id,
        use_oauth=use_oauth,
        cacert=cacert,
        rest_url=rest_url,
    )
