# Portfolio checker

Python CLI tool to **read brokerage holdings** from several brokers (OAuth where required). It is intended to run on a small home server (e.g. **Raspberry Pi**) and to feed a daily portfolio summary (returns, news, etc.—to be built on top of these connectors).

**This is not financial advice.** Broker APIs and third-party client libraries can change; use at your own risk and comply with each broker’s terms.

## Requirements

- **Python 3.11+**
- Accounts and API access as required by each broker (surveys, app approval, funded accounts, etc.)

## Install

```bash
git clone https://github.com/usistan/cursor-portfolio-tracker.git
cd cursor-portfolio-tracker
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
# or: pip install -r requirements.txt
```

Entry point: `portfolio-checker` (see `portfolio-checker --help`).

## Configuration

Copy `env.example` to `.env` and fill in only the brokers you use.

```bash
cp env.example .env
```

Keep token files **private** (`chmod 600` on Linux/macOS) and **never commit** them (they are listed in `.gitignore`).

---

## E\*TRADE (`etrade`)

Uses **OAuth 1.0a** and [`pyetrade`](https://pypi.org/project/pyetrade/). Sandbox vs production is controlled by `ETRADE_SANDBOX` (OAuth hosts differ).

| Variable | Description |
|----------|-------------|
| `ETRADE_CONSUMER_KEY` / `ETRADE_CONSUMER_SECRET` | From the [E\*TRADE developer portal](https://developer.etrade.com/getting-started) |
| `ETRADE_SANDBOX` | `true` = sandbox (`apisb.etrade.com`), `false` = production |
| `ETRADE_TOKEN_PATH` | File for access tokens (default `.etrade_tokens.json`) |

**Commands**

```bash
portfolio-checker etrade diagnose    # env check, no API call
portfolio-checker etrade authorize   # browser URL + verifier → token file
portfolio-checker etrade accounts      # raw account list (JSON)
portfolio-checker etrade portfolio     # accounts + positions (JSON)
portfolio-checker etrade portfolio --renew   # renew access token before fetch
```

**Notes:** Production keys often require completing the developer survey and agreement. Keys shown as **pending approval** will fail OAuth until approved.

---

## Charles Schwab (`schwab`)

Uses **OAuth 2.0** via [`schwab-py`](https://schwab-py.readthedocs.io/) (community client). Register an app at [developer.schwab.com](https://developer.schwab.com/) and set the **callback URL** exactly as in the portal (e.g. `https://127.0.0.1:8182`).

| Variable | Description |
|----------|-------------|
| `SCHWAB_API_KEY` / `SCHWAB_APP_SECRET` | App credentials |
| `SCHWAB_CALLBACK_URL` | Must match the registered redirect URI |
| `SCHWAB_TOKEN_PATH` | OAuth token file (default `.schwab_token.json`) |

**Commands**

```bash
portfolio-checker schwab diagnose      # env check
portfolio-checker schwab authorize     # default: manual URL flow (SSH / Pi friendly)
portfolio-checker schwab authorize --login-flow   # local browser + callback server
portfolio-checker schwab accounts      # linked accounts + positions (JSON)
portfolio-checker schwab portfolio     # per-account hashes + details (JSON)
```

---

## Interactive Brokers (`ibkr`, incl. UK)

Uses the **Client Portal Web API** via [`ibind`](https://github.com/Voyz/ibind). **UK and other regions** use the same API surface.

**Typical setup:** run the **Client Portal Gateway** locally (default base URL `https://127.0.0.1:5000/v1/api/`), log in with IB Key in the browser, then run the CLI. Alternatives: **OAuth 1.0a** headless config using `IBIND_*` variables (see ibind’s wiki).

| Variable | Description |
|----------|-------------|
| `IBKR_GATEWAY_HOST` / `IBKR_GATEWAY_PORT` | Gateway listen address (defaults `127.0.0.1:5000`) |
| `IBKR_BASE_ROUTE` | API prefix (default `/v1/api/`) |
| `IBKR_REST_URL` | Optional full base URL (overrides host/port) |
| `IBKR_ACCOUNT_ID` | Optional; if unset, account IDs come from `/portfolio/accounts` |
| `IBKR_CACERT` | Path to CA bundle for TLS; empty often means no verify (local gateway only) |
| `IBKR_USE_OAUTH` | `true` to use OAuth 1.0a (`IBIND_OAUTH1A_*`, etc.) |

**Commands**

```bash
portfolio-checker ibkr diagnose   # show gateway vs OAuth settings
portfolio-checker ibkr auth         # authentication status (needs active gateway session)
portfolio-checker ibkr accounts     # raw /portfolio/accounts
portfolio-checker ibkr portfolio    # accounts + paginated positions (JSON)
```

Documentation: [IBKR Client Portal Web API](https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/).

---

## Project layout

```
src/portfolio_checker/
  cli.py            # CLI entry
  config.py         # env loading for all brokers
  etrade_oauth.py   # E*TRADE OAuth hosts (sandbox vs prod)
  etrade_service.py / etrade_parse.py
  schwab_service.py
  ibkr_service.py
  token_store.py    # E*TRADE token file helpers
```

## License / third-party libraries

- **pyetrade**, **schwab-py**, **ibind** are third-party packages; see their licenses and terms.
- This repository’s code is provided as-is for automation and personal use.
