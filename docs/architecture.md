# Scout architecture and current limits

The repository started without application code or an established stack. The
current local MVP uses dependency-free runtime modules, SQLite, and an optional
pytest installation so the core can run without broker, database-server, or MCP
credentials.

## Market data

`scout.data` accepts `Bar` objects with timezone-aware timestamps and validates
supported instrument identifiers, finite positive prices, nonnegative volume,
OHLC relationships, uniqueness, and chronological ordering. It deliberately
does not repair gaps, infer a session calendar, adjust corporate actions, or
fetch data. Dataset provenance is represented by `DatasetInfo`; callers must
retain it alongside results. A production ingestion adapter still needs to
validate source schema, coverage, freshness, session boundaries, and licence.
Only `NSE:NIFTY50` and `NSE:NIFTYBANK` are currently accepted. `scout.ingestion`
provides a CSV adapter with dataset version, source identity, ingestion time,
coverage, and missing-interval warnings. It does not silently fill gaps or
perform corporate-action adjustments.

`scout.market.YahooFinanceProvider` reads Yahoo Finance chart data for `^NSEI`
and `^NSEBANK`, validates returned bars, and returns provenance. The browser
requests quotes only after the user clicks Connect quote. The feed may be
delayed or rate-limited and is not treated as a licensed execution feed. No
quote is fabricated when the provider is unavailable. Paper orders use the
latest validated quote and remain inside `PaperPortfolio`.

## Backtest assumptions

`scout.strategy.MovingAverageCross` is the only supported strategy. It uses
close-based simple moving averages and long-only entry/exit signals. A signal
computed from a completed bar executes at the next bar's open. Costs apply
proportional fees and slippage on both sides. Quantity is fixed; there is no
margin, shorting, taxes, partial fills, corporate-action handling, stop order,
or exchange-specific charge schedule. An open position is marked at the final
close rather than force-closed. The chronological split is fixed in advance;
OOS uses the same parameters and includes trades entered after the split.
Results must not be interpreted as a forecast or evidence of future profit.

## Tools and safety

`scout.tools.ToolRegistry` is an explicit registry with input/output checks,
permission checks, and a call budget. It is not exposed to a model and is not
an MCP server. `scout.persistence` stores local JSON records and audit events.
`scout.knowledge` keeps source identity, dates, versions, and an untrusted
content warning separate from deterministic calculations. `scout.model` is an
opt-in Hugging Face adapter with timeouts, bounded retries, and response limits.
There is no arbitrary code execution, shell tool, filesystem tool, or live
broker path.

`scout.idea_checker` is the beginner-facing deterministic idea checker. It
checks bounded entry/exit text, stop-loss, target, and per-trade risk before a
backtest. It is not an LLM and cannot place orders.

The browser Ctrl+Space handler opens the local Scout Guide drawer. The chat
endpoint intentionally reports model unavailability in this build so prompts
remain local. Voice capture is shown as disabled because browser speech APIs
may send audio to an unspecified third-party service; it requires an explicitly
approved speech provider before implementation.

Fine-tuning, RAG corpus ingestion from remote sources, and time-series
forecasting are not implemented. The model adapter is for bounded explanation
or structured proposals only; it is never the source of financial metrics.

`scout.recommendations` enforces the documented state machine server-side;
approval is only possible from `AWAITING_APPROVAL`. `scout.discovery` limits
families, candidates, and wall-clock budget. `scout.automation` records
explicitly requested monitoring runs; it does not run an unbounded agent loop.

## Next implementation stages

1. Add Indian session calendars, holiday handling, corporate-action metadata,
   and a licensed live/historical provider adapter.
2. Replace the generic fee/slippage inputs with a tested transaction-cost model
   that includes applicable exchange, statutory, and instrument metadata.
3. Add authentication/authorization and durable portfolio/automation service
   integration around the existing local APIs.
4. Add a real scheduler and event queue around the bounded automation service.
5. Add MCP transport only when external interoperability justifies it; handlers
   should invoke these same services rather than reimplement calculations.
6. Add a frontend navigation surface for portfolio, discovery, monitoring,
   activity, integrations, and settings beyond the current backtest page.
