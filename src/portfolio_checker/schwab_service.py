"""Charles Schwab Trader API über ``schwab-py`` (OAuth 2.0)."""

from __future__ import annotations

import logging
from typing import Any

from schwab.auth import client_from_token_file

from portfolio_checker.config import SchwabSettings

LOGGER = logging.getLogger(__name__)


def make_client(settings: SchwabSettings):
    """Lädt einen Schwab-``Client`` aus der Token-Datei (Refresh inkl.)."""
    return client_from_token_file(
        str(settings.token_path),
        settings.api_key,
        settings.app_secret,
        enforce_enums=True,
    )


def fetch_portfolio_snapshot(settings: SchwabSettings) -> dict[str, Any]:
    """
    Liest Account-Nummern/Hashes und ruft pro Konto ``get_account`` mit Positions-Feld auf.
    Antworten sind die JSON-Strukturen der Schwab-API.
    """
    client = make_client(settings)
    r_nums = client.get_account_numbers()
    r_nums.raise_for_status()
    numbers = r_nums.json()
    if not isinstance(numbers, list):
        numbers = []

    snapshot: dict[str, Any] = {
        "broker": "schwab",
        "accounts": [],
    }

    pos_field = client.Account.Fields.POSITIONS
    for row in numbers:
        if not isinstance(row, dict):
            continue
        account_hash = row.get("hashValue")
        if not account_hash:
            LOGGER.warning("Eintrag ohne hashValue übersprungen: %s", row)
            continue
        acc_num = row.get("accountNumber")
        r_acc = client.get_account(account_hash, fields=[pos_field])
        r_acc.raise_for_status()
        body = r_acc.json()
        snapshot["accounts"].append(
            {
                "accountNumber": acc_num,
                "accountHash": account_hash,
                "account": body,
            }
        )

    return snapshot
