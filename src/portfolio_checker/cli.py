from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys

from requests_oauthlib.oauth1_session import TokenRequestDenied

from portfolio_checker.config import (
    _clean_credential,
    load_env_files,
    load_etrade_settings,
    load_ibkr_settings,
    load_schwab_settings,
)
from portfolio_checker.etrade_oauth import EtradeOAuth, oauth_api_base
from portfolio_checker.etrade_service import (
    fetch_portfolio_snapshot,
    list_accounts_json,
    renew_access_token,
)
from portfolio_checker.ibkr_service import authentication_status as ibkr_auth_status
from portfolio_checker.ibkr_service import fetch_portfolio_snapshot as ibkr_fetch_portfolio
from portfolio_checker.ibkr_service import make_client as ibkr_make_client
from portfolio_checker.schwab_service import fetch_portfolio_snapshot as schwab_fetch_portfolio
from portfolio_checker.schwab_service import make_client as schwab_make_client
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
    load_env_files()
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


def _cmd_schwab_diagnose() -> int:
    load_env_files()
    now = datetime.datetime.now().astimezone()
    k = _clean_credential(os.environ.get("SCHWAB_API_KEY", ""))
    s = _clean_credential(os.environ.get("SCHWAB_APP_SECRET", ""))
    cb = _clean_credential(os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182"))
    raw_path = os.environ.get("SCHWAB_TOKEN_PATH", ".schwab_token.json").strip()
    print("Schwab Diagnose (keine API-Verbindung)")
    print(f"  Lokale Zeit: {now.isoformat()}")
    print(f"  SCHWAB_CALLBACK_URL: {cb or '(nicht gesetzt)'}")
    print(f"  API Key Länge: {len(k)} Zeichen")
    if len(k) >= 8:
        print(f"  API Key (Maskierung): {k[:4]}…{k[-4:]}")
    elif k:
        print("  API Key: (kurz — prüfen)")
    else:
        print("  API Key: (nicht gesetzt)")
    print(f"  App Secret Länge: {len(s)} Zeichen")
    if not s:
        print("  App Secret: (nicht gesetzt)")
    print(f"  Token-Datei: {raw_path}")
    print(
        "  Hinweis: Callback-URL muss exakt der App auf developer.schwab.com entsprechen "
        "(z. B. https://127.0.0.1:8182)."
    )
    return 0


def _cmd_schwab_authorize(args: argparse.Namespace) -> int:
    from schwab.auth import client_from_login_flow, client_from_manual_flow

    settings = load_schwab_settings()
    tp = str(settings.token_path)
    print(f"Callback-URL (muss zum Portal passen): {settings.callback_url}")
    if args.login_flow:
        client_from_login_flow(
            settings.api_key,
            settings.app_secret,
            settings.callback_url,
            tp,
            enforce_enums=True,
            callback_timeout=args.callback_timeout,
        )
    else:
        print(
            "Manueller OAuth-Flow (für SSH/Pi ohne Browser auf dem Gerät). "
            "Anweisungen folgen.\n",
        )
        client_from_manual_flow(
            settings.api_key,
            settings.app_secret,
            settings.callback_url,
            tp,
            enforce_enums=True,
        )
    print(f"Token gespeichert unter {tp}")
    return 0


def _cmd_schwab_accounts() -> int:
    settings = load_schwab_settings()
    client = schwab_make_client(settings)
    r = client.get_accounts(fields=[client.Account.Fields.POSITIONS])
    r.raise_for_status()
    json.dump(r.json(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_schwab_portfolio() -> int:
    settings = load_schwab_settings()
    snap = schwab_fetch_portfolio(settings)
    json.dump(snap, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_ibkr_diagnose() -> int:
    load_env_files()
    now = datetime.datetime.now().astimezone()
    try:
        s = load_ibkr_settings()
    except RuntimeError as e:
        print(f"Konfiguration: {e}", file=sys.stderr)
        return 1
    print("Interactive Brokers (Client Portal API, ibind)")
    print(f"  Lokale Zeit: {now.isoformat()}")
    print(f"  IBKR_USE_OAUTH: {s.use_oauth}")
    if s.use_oauth:
        print("  Modus: OAuth 1.0a (siehe IBIND_OAUTH1A_* in der ibind-Dokumentation)")
    else:
        url = s.rest_url or f"https://{s.host}:{s.port}{s.base_route}"
        print(f"  Gateway-URL: {url}")
    print(
        f"  IBKR_ACCOUNT_ID: {s.account_id or '(auto aus /portfolio/accounts)'}",
    )
    print(
        "\n  Hinweis: Gateway betreiben, im Browser anmelden (IB Key), dann z. B. "
        "`portfolio-checker ibkr auth`.",
    )
    return 0


def _cmd_ibkr_auth() -> int:
    settings = load_ibkr_settings()
    data = ibkr_auth_status(settings)
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_ibkr_accounts() -> int:
    settings = load_ibkr_settings()
    client = ibkr_make_client(settings)
    r = client.portfolio_accounts()
    out = r.data
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_ibkr_portfolio() -> int:
    settings = load_ibkr_settings()
    snap = ibkr_fetch_portfolio(settings)
    json.dump(snap, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="portfolio-checker",
        description="Portfolio-Checker (E*TRADE, Schwab, Interactive Brokers, …).",
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

    p_sc = sub.add_parser("schwab", help="Charles Schwab Trader API (OAuth 2.0)")
    sc_sub = p_sc.add_subparsers(dest="schwab_cmd", required=True)

    sc_sub.add_parser(
        "diagnose",
        help="Umgebung prüfen (Callback-URL, Key-Längen) ohne API-Call",
    )

    p_auth = sc_sub.add_parser(
        "authorize",
        help="OAuth: Token-Datei erzeugen (Standard: manueller Flow; Pi/SSH-freundlich)",
    )
    p_auth.add_argument(
        "--login-flow",
        action="store_true",
        help="Lokalen Browser + Callback-Server nutzen (auf dem Pi oft ungeeignet)",
    )
    p_auth.add_argument(
        "--callback-timeout",
        type=float,
        default=300.0,
        metavar="SEC",
        help="Nur mit --login-flow: Timeout auf Redirect (Default: 300)",
    )

    sc_sub.add_parser(
        "accounts",
        help="Alle verknüpften Konten inkl. Positions-Feld (Roh-JSON der API)",
    )

    sc_sub.add_parser(
        "portfolio",
        help="Konten mit Hash + Positions-Details (normalisiertes JSON)",
    )

    p_ib = sub.add_parser(
        "ibkr",
        help="Interactive Brokers Client Portal Web API (Gateway oder OAuth, ibind)",
    )
    ib_sub = p_ib.add_subparsers(dest="ibkr_cmd", required=True)

    ib_sub.add_parser(
        "diagnose",
        help="Gateway-/OAuth-Einstellungen anzeigen (ohne API-Call)",
    )
    ib_sub.add_parser(
        "auth",
        help="Authentifizierungsstatus (Session/Gateway)",
    )
    ib_sub.add_parser(
        "accounts",
        help="Rohdaten: /portfolio/accounts",
    )
    ib_sub.add_parser(
        "portfolio",
        help="Konten + alle Positionen (JSON)",
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

    if args.command == "schwab":
        if args.schwab_cmd == "diagnose":
            return _cmd_schwab_diagnose()
        if args.schwab_cmd == "authorize":
            return _cmd_schwab_authorize(args)
        if args.schwab_cmd == "accounts":
            return _cmd_schwab_accounts()
        if args.schwab_cmd == "portfolio":
            return _cmd_schwab_portfolio()

    if args.command == "ibkr":
        if args.ibkr_cmd == "diagnose":
            return _cmd_ibkr_diagnose()
        if args.ibkr_cmd == "auth":
            return _cmd_ibkr_auth()
        if args.ibkr_cmd == "accounts":
            return _cmd_ibkr_accounts()
        if args.ibkr_cmd == "portfolio":
            return _cmd_ibkr_portfolio()

    raise RuntimeError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
