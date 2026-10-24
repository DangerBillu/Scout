# Scout

Scout is an early-stage, paper-trading research application for Indian markets.
The repository provides a local Python MVP for validating Indian-market bars,
running a reproducible moving-average paper backtest, bounded strategy
discovery, paper portfolio risk checks, source-grounded knowledge records,
recommendation approvals, and auditable local persistence. It does not connect
to a broker or place orders.

## Current capabilities

- Strict OHLCV validation and dataset provenance metadata.
- NIFTY 50 and NIFTY BANK instrument identifiers (additional instruments need
  explicit metadata).
- Long-only moving-average crossover backtests with explicit per-side
  proportional transaction costs and slippage.
- Deterministic chronological train/test split and summary risk metrics.
- CSV source-adapter quality reports with provenance and missing-interval warnings.
- Bounded moving-average discovery with candidate limits and time budgets.
- Paper portfolio snapshots with deterministic exposure and stale-price alerts.
- Server-side recommendation state transitions with explicit approval and audit events.
- Validated model configuration and a bounded Hugging Face adapter; model failures
  do not stop quantitative services.
- A small typed internal tool registry; MCP transport remains a documented extension point.

All prices and bars must come from a licensed source supplied by the operator.
Scout does not fetch or fabricate market data. Synthetic bars may be used only
in tests and must be labelled as fixtures.

## Run

Python 3.11 or later is required. The core has no third-party runtime
dependencies.

Start the local UI:

```powershell
# Optional: create and activate a virtual environment
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python -m scout
```

Open **http://127.0.0.1:8000**. Paste bars from a licensed source in the CSV
box with this header:

```csv
timestamp,open,high,low,close,volume
```

Timestamps must be ISO 8601 with a timezone. Scout rejects malformed OHLC,
duplicate or unordered timestamps, unsupported instruments, and invalid values.
It does not fill missing bars. Stop the server with Ctrl+C.

To change the port in PowerShell:

```powershell
$env:SCOUT_PORT = "8080"
python -m scout
```

The server binds to `127.0.0.1` by default. It has no authentication for
network access; keep it local.

## Hugging Face configuration

Copy `.env.example` to `.env` and set `HF_TOKEN`. `.env` is ignored by Git.
The model adapter reads the token only on the backend when a caller explicitly
uses `HuggingFaceAdapter`. The UI never receives it. The default local UI does
not call the model. Provider/model errors are bounded and do not disable the
deterministic backtest or risk checks.

## Local API surface

The standard-library server exposes the UI plus these local endpoints:

- `GET /health` and `GET /api/integrations/status`.
- `GET /api/models/config` (redacted model configuration).
- `GET /api/data/instruments` and `GET /api/activity`.
- `GET /api/market/status`, `GET /api/market/quote`, and `GET /api/market/candles`.
- `POST /api/paper/orders` for simulated fills only.
- `POST /api/backtest` and `POST /api/discovery`.
- `POST /api/ideas/check` for the beginner idea checker.
- `POST /api/agent/chat` for the local chat drawer; external model calls are disabled in this build.
- `POST /api/data/validate` for CSV schema, provenance, and gap checks.
- `GET/POST /api/recommendations` and `POST /api/recommendations/transition`.
- `GET/POST /api/automations` for bounded job configuration.
- `GET /api/knowledge/search?q=...` for registered trusted documents.

These endpoints are intended for local paper research. The server has no
authentication and binds to `127.0.0.1` by default; do not expose it to a
network without adding authentication and authorization.

To connect live quotes, set `TWELVE_DATA_API_KEY` in `.env`, confirm the
provider's exact NIFTY symbols, and click **Connect quote** in the terminal. The
server fetches and validates the quote only on that explicit action; blank or
invalid provider responses remain unavailable. The provider's plan determines
whether a symbol is real-time or delayed.

## Tests

```powershell
python -m unittest discover -s tests -v
```

See `docs/architecture.md` for backtest assumptions and the remaining
implementation limits.
