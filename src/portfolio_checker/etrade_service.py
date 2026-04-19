from __future__ import annotations

import logging
from typing import Any

import pyetrade
from requests_oauthlib import OAuth1Session

from portfolio_checker.config import EtradeSettings
from portfolio_checker.etrade_oauth import oauth_api_base
from portfolio_checker.etrade_parse import parse_account_list, parse_portfolio_page

LOGGER = logging.getLogger(__name__)


def make_accounts_client(
    settings: EtradeSettings, tokens: dict[str, str]
) -> pyetrade.ETradeAccounts:
    return pyetrade.ETradeAccounts(
        settings.consumer_key,
        settings.consumer_secret,
        tokens["oauth_token"],
        tokens["oauth_token_secret"],
        dev=settings.sandbox,
    )


def renew_access_token(settings: EtradeSettings, tokens: dict[str, str]) -> None:
    """Erneuert den Access Token (E*TRADE: u. a. nach Inaktivität sinnvoll)."""
    base = oauth_api_base(settings.sandbox)
    url = f"{base}/oauth/renew_access_token"
    session = OAuth1Session(
        settings.consumer_key,
        settings.consumer_secret,
        tokens["oauth_token"],
        tokens["oauth_token_secret"],
        signature_type="AUTH_HEADER",
    )
    resp = session.get(url)
    resp.raise_for_status()


def list_accounts_json(settings: EtradeSettings, tokens: dict[str, str]) -> dict:
    client = make_accounts_client(settings, tokens)
    return client.list_accounts(resp_format="json")


def fetch_portfolio_snapshot(
    settings: EtradeSettings,
    tokens: dict[str, str],
    *,
    renew_first: bool = False,
    page_size: int = 100,
    portfolio_view: str = "PERFORMANCE",
) -> dict[str, Any]:
    """
    Liest alle Konten und paginiert die Portfolio-Positionen pro Konto.

    portfolio_view: QUICK, PERFORMANCE, COMPLETE (E*TRADE-Dokumentation).
    """
    if renew_first:
        renew_access_token(settings, tokens)

    client = make_accounts_client(settings, tokens)
    accounts_raw = client.list_accounts(resp_format="json")
    accounts = parse_account_list(accounts_raw)

    snapshot: dict[str, Any] = {
        "broker": "etrade",
        "sandbox": settings.sandbox,
        "accounts": [],
    }

    for acc in accounts:
        account_id_key = acc.get("accountIdKey") or acc.get("accountIdkey")
        if not account_id_key:
            LOGGER.warning("Account ohne accountIdKey übersprungen: %s", acc)
            continue

        meta = {
            "accountIdKey": account_id_key,
            "accountId": acc.get("accountId"),
            "accountName": acc.get("accountName"),
            "accountDesc": acc.get("accountDesc"),
            "accountMode": acc.get("accountMode"),
            "accountType": acc.get("accountType"),
        }

        positions_out: list[dict[str, Any]] = []
        page = 1
        while True:
            payload = client.get_account_portfolio(
                account_id_key,
                count=page_size,
                page_number=page,
                market_session="REGULAR",
                totals_required=True,
                lots_required=False,
                view=portfolio_view,
                resp_format="json",
            )
            info = parse_portfolio_page(payload)
            batch = info["positions"]
            if not batch:
                break
            for p in batch:
                positions_out.append(_normalize_position(meta, p))
            total_pages = info.get("totalNoOfPages")
            if isinstance(total_pages, int) and total_pages > 0:
                if page >= total_pages:
                    break
                page += 1
                continue
            if len(batch) < page_size:
                break
            page += 1

        snapshot["accounts"].append({**meta, "positions": positions_out})

    return snapshot


def _normalize_position(account_meta: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    product = raw.get("Product") or raw.get("product") or {}
    sym = product.get("symbol") or product.get("Symbol")
    typ = product.get("typeCode") or product.get("type")
    row: dict[str, Any] = {
        "accountIdKey": account_meta.get("accountIdKey"),
        "accountName": account_meta.get("accountName"),
        "symbol": sym,
        "productType": typ,
        "quantity": _to_float(raw.get("quantity") or raw.get("Quantity")),
    }
    # optionale Felder je nach view
    for k in (
        "totalGainLoss",
        "totalGain",
        "totalGainLossPct",
        "daysGain",
        "daysGainPct",
        "marketValue",
        "costBasis",
        "averagePrice",
        "lastPrice",
    ):
        if k in raw:
            row[k] = raw[k]
    # Kleinbuchstaben-Varianten
    for src, dst in (
        ("totalGainLoss", "totalGainLoss"),
        ("totalGainLossPct", "totalGainLossPct"),
    ):
        lk = src.lower()
        if lk in raw and dst not in row:
            row[dst] = raw[lk]
    return row


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
