from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys

from dotenv import load_dotenv
from requests_oauthlib.oauth1_session import TokenRequestDenied

from portfolio_checker.config import _clean_credential, load_etrade_settings
from portfolio_checker.etrade_oauth import EtradeOAuth, oauth_api_base
from portfolio_checker.etrade_service import (
    fetch_portfolio_snapshot,
    list_accounts_json,
    renew_access_token,
)
from portfolio_checker.token_store import load_tokens, save_tokens


def _etrade_consumer_key_rejected_help() -> None:
    print(
        "\nE*TRADE meldet: oauth_problem=consumer_key_rejected\n"
        "\n"
        "Das Consumer-Key/Secret-Paar wird für diesen OAuth-Host abgelehnt. Häufige Ursachen:\n"
        "\n"
        "  • Falscher oder alter Consumer Secret (muss exakt zum Key im Developer-Portal passen).\n"
        "  • Sandbox-Key von us.etrade.com/etx/ris/apikey — dann ETRADE_SANDBOX=true setzen und\n"
        "    erneut autorisieren (OAuth-Host wechselt auf apisb.etrade.com).\n"
        "  • PROD-Key mit „pending approval“ im Portal: OAuth funktioniert erst nach Freigabe durch\n"
        "    E*TRADE — bis dahin consumer_key_rejected.\n"
        "  • Live/Production-Key: Survey + API Agreement müssen erledigt sein (Getting Started).\n"
        "    Vendor-Keys können „Inactive“ sein, bis E*TRADE sie freischaltet.\n"
        "  • Systemzeit auf dem Pi: OAuth verlangt korrekte Uhrzeit (NTP), Abweichung max. ~5 Minuten.\n"
        "\n"
        "Prüfen: portfolio-checker etrade diagnose\n"
        "Doku: https://developer.etrade.com/getting-started\n",
        file=sys.stderr,
    )


def _cmd_etrade_diagnose() -> int:
    load_dotenv()
    now = datetime.datetime.now().astimezone()
    sandbox = os.environ.get("ETRADE_SANDBOX", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    raw_path = os.environ.get("ETRADE_TOKEN_PATH", ".etrade_tokens.json").strip()
    k = _clean_credential(os.environ.get("ETRADE_CONSUMER_KEY", ""))
    s = _clean_credential(os.environ.get("ETRADE_CONSUMER_SECRET", ""))
    print("E*TRADE Diagnose (keine Netzwerk-Anfrage)")
    print(f"  Lokale Zeit: {now.isoformat()}")
    print(f"  ETRADE_SANDBOX: {sandbox}")
    print(f"  OAuth request_token Host: {oauth_api_base(sandbox)}")
    print(f"  Consumer Key Länge: {len(k)} Zeichen")
    if len(k) >= 8:
        print(f"  Consumer Key (Maskierung): {k[:4]}…{k[-4:]}")
    elif k:
        print("  Consumer Key: (verkürzt — prüfen)")
    else:
        print("  Consumer Key: (nicht gesetzt)")
    print(f"  Consumer Secret Länge: {len(s)} Zeichen")
    if not s:
        print("  Consumer Secret: (nicht gesetzt)")
    print(f"  Token-Datei: {raw_path}")
    return 0


def _cmd_etrade_authorize() -> int:
    settings = load_etrade_settings()
    mode = "SANDBOX (apisb.etrade.com)" if settings.sandbox else "PRODUCTION (api.etrade.com)"
    print(f"OAuth-Modus: {mode}")
    oauth = EtradeOAuth(
        settings.consumer_key,
        settings.consumer_secret,
        sandbox=settings.sandbox,
    )
    try:
        url = oauth.get_request_token()
    except TokenRequestDenied as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        _etrade_consumer_key_rejected_help()
        return 1
    print("1) Diese URL im Browser öffnen und bei E*TRADE anmelden:")
    print(url)
    print("2) Nach Freigabe den Verification Code (Verifier) eingeben.")
    verifier = input("Verifier: ").strip()
    if not verifier:
        print("Abbruch: kein Verifier.", file=sys.stderr)
        return 1
    try:
        tokens = oauth.get_access_token(verifier)
    except TokenRequestDenied as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        _etrade_consumer_key_rejected_help()
        return 1
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

    et_sub.add_parser(
        "diagnose",
        help="Prüft .env/Umgebung (ohne API-Call): Sandbox-Modus, Key-Längen, Uhrzeit",
    )

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
        if args.etrade_cmd == "diagnose":
            return _cmd_etrade_diagnose()
        if args.etrade_cmd == "accounts":
            return _cmd_etrade_accounts()
        if args.etrade_cmd == "portfolio":
            return _cmd_etrade_portfolio(args)

    raise RuntimeError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
