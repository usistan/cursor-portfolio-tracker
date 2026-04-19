from __future__ import annotations

from typing import Any


def _as_list(x: Any) -> list:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def parse_account_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrahiert Account-Einträge aus der List-Accounts-JSON-Antwort."""
    root = payload
    for key in ("AccountListResponse", "accountListResponse"):
        if key in payload:
            root = payload[key]
            break
    accounts = root
    for key in ("Accounts", "accounts"):
        if key in accounts:
            accounts = accounts[key]
            break
    for key in ("Account", "account"):
        if key in accounts:
            accounts = accounts[key]
            break
    return _as_list(accounts)


def parse_portfolio_positions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrahiert Positionen aus get_account_portfolio (JSON)."""
    page = parse_portfolio_page(payload)
    return page["positions"]


def parse_portfolio_page(payload: dict[str, Any]) -> dict[str, Any]:
    """Eine Portfolio-Seite: Positionen plus Paginierung aus AccountPortfolio."""
    root = payload
    for key in ("PortfolioResponse", "portfolioResponse"):
        if key in payload:
            root = payload[key]
            break
    ap = root
    for key in ("AccountPortfolio", "accountPortfolio"):
        if key in ap:
            ap = ap[key]
            break
    blocks = _as_list(ap)
    positions: list[dict[str, Any]] = []
    total_pages: int | None = None
    next_page: str | None = None
    for block in blocks:
        if total_pages is None:
            raw_tp = block.get("totalNoOfPages") or block.get("totalPages")
            if raw_tp is not None:
                try:
                    total_pages = int(raw_tp)
                except (TypeError, ValueError):
                    total_pages = None
        if next_page is None:
            next_page = block.get("nextPageNo") or block.get("nextPage")
        pos = block
        for key in ("Position", "position"):
            if key in pos:
                pos = pos[key]
                break
        positions.extend(_as_list(pos))
    return {
        "positions": positions,
        "totalNoOfPages": total_pages,
        "nextPageNo": next_page,
    }
