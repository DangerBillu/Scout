# Scout architecture and current limits

This repository started without application code or an established stack. The
first implementation pass uses dependency-free Python modules so the core can
run without model, data-provider, database, broker, or MCP credentials.

## Market data

`scout.data` accepts `Bar` objects with timezone-aware timestamps and validates
supported instrument identifiers, finite positive prices, nonnegative volume,
OHLC relationships, uniqueness, and chronological ordering. It deliberately
does not repair gaps, infer a session calendar, adjust corporate actions, or
fetch data. Dataset provenance is represented by `DatasetInfo`; callers must
retain it alongside results. A production ingestion adapter still needs to
validate source schema, coverage, freshness, session boundaries, and licence.
Only `NSE:NIFTY50` and `NSE:NIFTYBANK` are currently accepted.

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

`scout.tools.ToolRegistry` is an extension point with explicit registration and
permission checks. It is not exposed to a model and is not an MCP server. Before
production use it needs typed per-tool schemas, output validation, audit records,
timeouts, budgets, idempotency for state changes, authentication, and tests for
untrusted tool output. No live broker execution, model adapter, document
retrieval, persistence, monitoring scheduler, recommendation workflow, or
strategy discovery is implemented.

## Next implementation stages

1. Define source adapters, provenance persistence, Indian session calendars,
   and missing-interval quality reports against an approved licensed source.
2. Add a tested transaction-cost model with applicable exchange, statutory,
   and instrument metadata.
3. Add persistence/API and paper portfolio services with deterministic risk
   limits.
4. Add bounded chronological discovery and server-side recommendation states.
5. Add configurable model/retrieval integrations only after source and provider
   configuration can be validated. MCP should expose existing services rather
   than reimplement them.
