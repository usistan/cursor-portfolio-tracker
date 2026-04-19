from __future__ import annotations

import argparse
import json
import logging
import sys

import pyetrade

from portfolio_checker.config import load_etrade_settings
from portfolio_checker.etrade_service import (
    fetch_portfolio_snapshot,
    list_accounts_json,
    renew_access_token,
)
from portfolio_checker.token_store import load_tokens, save_tokens


def _cmd_etrade_authorize() -> int:
    settings = load_etrade_settings()
    oauth = pyetrade.ETradeOAuth(settings.consumer_key, settings.consumer_secret)
    url = oauth.get_request_token()
    print("1) Diese URL im Browser öffnen und bei E*TRADE anmelden:")
    print(url)
    print("2) Nach Freigabe den Verification Code (Verifier) eingeben.")
    verifier = input("Verifier: ").strip()
    if not verifier:
        print("Abbruch: kein Verifier.", file=sys.stderr)
        return 1
    tokens = oauth.get_access_token(verifier)
    save_tokens(
        settings.token_path,
        {
            "oauth_token": tokens["oauth_token"],
            "oauth_token_secret": tokens["oauth_token_secret"],
        },
    )
    print(f"Tokens gespeichert unter {settings.token_path} (Zugriff nur für dich empfohlen).")
    return 0


def _cmd_etrade_accounts() -> int:
    settings = load_etrade_settings()
    tokens = load_tokens(settings.token_path)
    data = list_accounts_json(settings, tokens)
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_etrade_portfolio(args: argparse.Namespace) -> int:
    settings = load_etrade_settings()
    tokens = load_tokens(settings.token_path)
    if args.renew:
        renew_access_token(settings, tokens)
    snap = fetch_portfolio_snapshot(
        settings,
        tokens,
        renew_first=False,
        portfolio_view=args.view,
    )
    json.dump(snap, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="portfolio-checker",
        description="Portfolio-Checker (Broker: E*TRADE zuerst).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug-Logging",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_et = sub.add_parser("etrade", help="E*TRADE API (OAuth 1.0a)")
    et_sub = p_et.add_subparsers(dest="etrade_cmd", required=True)

    et_sub.add_parser("authorize", help="OAuth: Browser-URL + Verifier, speichert Tokens")

    et_sub.add_parser("accounts", help="Rohdaten: List Accounts (JSON)")

    p_pf = et_sub.add_parser("portfolio", help="Alle Konten + Positionen (JSON)")
    p_pf.add_argument(
        "--renew",
        action="store_true",
        help="Vorher Access Token erneuern (E*TRADE Renew-Endpoint)",
    )
    p_pf.add_argument(
        "--view",
        default="PERFORMANCE",
        choices=("QUICK", "PERFORMANCE", "COMPLETE", "FUNDAMENTAL", "OPTIONSWATCH"),
        help="Portfolio-Ansicht (Default: PERFORMANCE)",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "etrade":
        if args.etrade_cmd == "authorize":
            return _cmd_etrade_authorize()
        if args.etrade_cmd == "accounts":
            return _cmd_etrade_accounts()
        if args.etrade_cmd == "portfolio":
            return _cmd_etrade_portfolio(args)

    raise RuntimeError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
