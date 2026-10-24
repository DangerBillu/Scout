# Scout

Scout is an early-stage, paper-trading research application for Indian markets.
The repository currently provides a dependency-free Python foundation for
validating market bars, validating a bounded strategy definition, and running a
reproducible moving-average paper backtest. It does not connect to a broker or
place orders.

## Current capabilities

- Strict OHLCV validation and dataset provenance metadata.
- NIFTY 50 and NIFTY BANK instrument identifiers (additional instruments need
  explicit metadata).
- Long-only moving-average crossover backtests with explicit per-side
  proportional transaction costs and slippage.
- Deterministic chronological train/test split and summary risk metrics.
- A small internal read-only tool registry; there is no MCP server yet.

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
There is no model adapter in this build yet, so Scout does not read or use the
token; it is reserved for future model integration.

## Tests

```powershell
python -m unittest discover -s tests -v
```

See `docs/architecture.md` for backtest assumptions and the remaining
implementation limits.
