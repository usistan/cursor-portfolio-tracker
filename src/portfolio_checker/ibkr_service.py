"""Interactive Brokers Client Portal Web API via ``ibind`` (REST).

UK-Konten nutzen dieselbe API wie andere IBKR-Regionen; die Anbindung ist
identisch. Typisch: ``Client Portal Gateway`` auf ``127.0.0.1:5000`` und
Browser-Login; optional OAuth 1.0a über Umgebungsvariablen ``IBIND_*``.
"""

from __future__ import annotations

import logging
from typing import Any

from ibind import IbkrClient

from portfolio_checker.config import IbkrSettings

LOGGER = logging.getLogger(__name__)


def make_client(settings: IbkrSettings) -> IbkrClient:
    if settings.use_oauth:
        from ibind.oauth.oauth1a import OAuth1aConfig

        return IbkrClient(
            account_id=settings.account_id,
            use_oauth=True,
            oauth_config=OAuth1aConfig(),
        )
    kw: dict[str, Any] = {
        "account_id": settings.account_id,
        "use_oauth": False,
        "cacert": settings.cacert,
    }
    if settings.rest_url:
        kw["url"] = settings.rest_url
    else:
        kw["host"] = settings.host
        kw["port"] = str(settings.port)
        kw["base_route"] = settings.base_route
    return IbkrClient(**kw)


def _extract_account_ids(portfolio_accounts_data: Any) -> list[str]:
    if portfolio_accounts_data is None:
        return []
    items: list[Any]
    if isinstance(portfolio_accounts_data, dict):
        inner = (
            portfolio_accounts_data.get("accounts")
            or portfolio_accounts_data.get("accountList")
            or portfolio_accounts_data.get("acct")
        )
        if inner is None:
            return []
        items = inner if isinstance(inner, list) else [inner]
    elif isinstance(portfolio_accounts_data, list):
        items = portfolio_accounts_data
    else:
        return []
    out: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        aid = it.get("id") or it.get("accountId") or it.get("account_id")
        if aid is not None:
            out.append(str(aid))
    return out


def _flatten_position_payload(data: Any) -> list[Any]:
    if data is None:
        return []
    if isinstance(data, dict):
        p = data.get("positions")
        if isinstance(p, list):
            return p
        if isinstance(p, dict):
            return [p]
        if not p and data:
            return [data] if data else []
        return []
    if isinstance(data, list):
        return data
    return []


def fetch_all_positions(client: IbkrClient, account_id: str) -> list[Any]:
    """Lädt alle Seiten der Positions-Liste (je bis zu 100 Einträge)."""
    merged: list[Any] = []
    page = 0
    while page < 1000:
        res = client.positions(account_id=account_id, page=page)
        rows = _flatten_position_payload(res.data)
        if not rows:
            break
        merged.extend(rows)
        if len(rows) < 100:
            break
        page += 1
    return merged


def fetch_portfolio_snapshot(settings: IbkrSettings) -> dict[str, Any]:
    """
    Ruft ``/portfolio/accounts`` auf (Pflicht vor anderen Portfolio-Calls),
    dann pro Konto alle Positions-Seiten.
    """
    client = make_client(settings)
    pa = client.portfolio_accounts()
    raw_accounts = pa.data
    ids = _extract_account_ids(raw_accounts)
    if not ids and settings.account_id:
        ids = [settings.account_id]
    if not ids:
        raise RuntimeError(
            "Keine Account-IDs ermittelt: /portfolio/accounts lieferte keine Konten "
            "und IBKR_ACCOUNT_ID ist nicht gesetzt. Gateway eingeloggt? Siehe "
            "`portfolio-checker ibkr auth`."
        )

    accounts_out: list[dict[str, Any]] = []
    for aid in ids:
        positions = fetch_all_positions(client, aid)
        accounts_out.append({"accountId": aid, "positions": positions})

    return {
        "broker": "interactive_brokers",
        "note": "UK- und andere IBKR-Konten: gleiche Client Portal API.",
        "portfolioAccounts": raw_accounts,
        "accounts": accounts_out,
    }


def authentication_status(settings: IbkrSettings) -> Any:
    client = make_client(settings)
    return client.authentication_status().data
