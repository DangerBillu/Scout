"""Local browser interface for trying Scout's deterministic paper backtest."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from math import isfinite
from urllib.parse import urlparse

from .backtest import run_backtest
from .data import Bar
from .strategy import MovingAverageCross


PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Scout · Paper Research</title>
  <style>
    :root{color-scheme:dark;--bg:#050505;--panel:#101412;--line:#27332e;--mint:#36E6A0;--muted:#a9b5ae;--white:#fff;--coral:#ff7770}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--white);font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}
    header{padding:26px max(24px,calc((100vw - 1160px)/2));border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
    .brand{font-size:22px;font-weight:750;letter-spacing:.04em}.brand span{color:var(--mint)}.tag{color:var(--mint);border:1px solid #246d50;border-radius:20px;padding:5px 12px;font-size:12px}
    main{max-width:1160px;margin:30px auto;padding:0 24px}.intro{margin-bottom:24px}.intro h1{font-size:30px;margin:0 0 5px}.muted{color:var(--muted)}
    .layout{display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:20px}.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px}.card h2{font-size:17px;margin:0 0 18px}
    label{display:block;font-size:13px;color:#d8e0db;margin:12px 0 6px}input,select,textarea{width:100%;border:1px solid #34443c;background:#090c0a;color:white;border-radius:8px;padding:10px 11px;font:inherit}textarea{min-height:260px;resize:vertical;font:12px/1.45 ui-monospace,Consolas,monospace}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.hint{font-size:12px;color:var(--muted);margin:7px 0}.button{margin-top:18px;width:100%;border:0;background:var(--mint);color:#04110b;border-radius:8px;padding:12px;font-weight:700;font-size:15px;cursor:pointer}.button:disabled{opacity:.6;cursor:wait}
    .empty{min-height:300px;display:grid;place-items:center;text-align:center;color:var(--muted)}.status{margin-top:12px;color:var(--coral);font-size:13px;white-space:pre-wrap}.results{display:none}.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{border:1px solid var(--line);padding:13px;border-radius:10px}.metric small{display:block;color:var(--muted)}.metric strong{font-size:20px;display:block;margin-top:4px}.positive{color:var(--mint)}.negative{color:var(--coral)}
    .table-wrap{overflow:auto;margin-top:20px}table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}th,td{text-align:right;padding:9px;border-bottom:1px solid var(--line)}th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-weight:500}.warning{margin-top:18px;border-left:3px solid #a8ed16;padding:9px 12px;color:var(--muted);font-size:12px}.pill{display:inline-block;border:1px solid var(--line);border-radius:20px;padding:3px 9px;margin:0 5px 8px 0;font-size:11px;color:var(--muted)}
    @media(max-width:800px){.layout{grid-template-columns:1fr}.intro h1{font-size:25px}.metric-grid{grid-template-columns:repeat(2,1fr)}header{padding:18px 24px}}
  </style>
</head>
<body>
  <header><div class="brand">SCOUT<span>.</span></div><div class="tag">PAPER RESEARCH · LOCAL</div></header>
  <main>
    <section class="intro"><h1>Backtest a strategy</h1><div class="muted">Run a deterministic moving-average crossover against your own OHLCV data.</div></section>
    <div class="layout">
      <section class="card">
        <h2>Run configuration</h2>
        <div class="row"><div><label for="instrument">Instrument</label><select id="instrument"><option value="NSE:NIFTY50">NIFTY 50</option><option value="NSE:NIFTYBANK">NIFTY BANK</option></select></div><div><label for="timeframe">Timeframe</label><select id="timeframe"><option>1d</option><option>5m</option><option>15m</option><option>1h</option></select></div></div>
        <div class="row"><div><label for="fast">Fast average period</label><input id="fast" type="number" min="2" max="499" value="10"></div><div><label for="slow">Slow average period</label><input id="slow" type="number" min="3" max="500" value="30"></div></div>
        <div class="row"><div><label for="capital">Initial capital (₹)</label><input id="capital" type="number" min="1" value="100000"></div><div><label for="quantity">Fixed quantity</label><input id="quantity" type="number" min="0.0001" step="any" value="1"></div></div>
        <div class="row"><div><label for="fee">Fee per side (%)</label><input id="fee" type="number" min="0" max="5" step="0.01" value="0.03"></div><div><label for="slippage">Slippage per side (%)</label><input id="slippage" type="number" min="0" max="5" step="0.01" value="0.05"></div></div>
        <label for="csv">Market bars (CSV)</label><textarea id="csv" spellcheck="false" placeholder="timestamp,open,high,low,close,volume&#10;Paste timezone-aware ISO 8601 bars from a licensed data source."></textarea>
        <p class="hint">Use one row per bar. Timestamps must include a timezone, for example an ISO 8601 timestamp ending in +05:30 or Z. Minimum: 2 bars and enough history for the slow average. No missing bars are filled.</p>
        <button class="button" id="run">Run paper backtest</button><div id="status" class="status" role="status"></div>
      </section>
      <section class="card">
        <h2>Results</h2>
        <div id="empty" class="empty"><div><div style="font-size:30px;color:#52635a">↗</div><div>Paste market bars and run a backtest.<br>Results and assumptions will appear here.</div></div></div>
        <div id="results" class="results"><div id="badges"></div><div id="metrics" class="metric-grid"></div><div class="table-wrap"><table><thead><tr><th>Trade</th><th>Entry</th><th>Exit</th><th>Gross P&amp;L</th><th>Costs</th><th>Net P&amp;L</th></tr></thead><tbody id="trades"></tbody></table></div><div id="warnings" class="warning"></div></div>
      </section>
    </div>
    <p class="hint" style="margin-top:20px">Research only. Simulated fills do not guarantee real execution. Scout does not place orders. The HF token setting is reserved for a future model adapter and is not used by this build.</p>
  </main>
<script>
const $=id=>document.getElementById(id); const fmt=n=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(n);
function parseCSV(text){const lines=text.trim().split(/\r?\n/).filter(Boolean);if(lines.length<3)throw Error('Enter a header and at least two market bars.');const head=lines.shift().split(',').map(x=>x.trim().toLowerCase());const required=['timestamp','open','high','low','close','volume'];if(required.some(x=>!head.includes(x)))throw Error('CSV header must include: '+required.join(', '));return lines.map((line,i)=>{const values=line.split(',');const row={};head.forEach((key,k)=>row[key]=values[k]?.trim());for(const key of required.slice(1)){row[key]=Number(row[key]);if(!Number.isFinite(row[key]))throw Error(`Row ${i+2}: ${key} must be a number.`);}return row;});}
function metric(label,value,cls=''){return `<div class="metric"><small>${label}</small><strong class="${cls}">${value}</strong></div>`;}
function render(data){$('empty').style.display='none';$('results').style.display='block';const m=data.metrics,o=data.out_of_sample;$('badges').innerHTML=`<span class="pill">${data.instrument}</span><span class="pill">${data.bars} bars</span><span class="pill">Dataset ${escapeHtml(data.dataset_version)}</span><span class="pill">OOS split at bar ${data.split_index+1}</span>`;$('metrics').innerHTML=metric('Net P&amp;L',fmt(m.net_pnl),m.net_pnl>=0?'positive':'negative')+metric('Return',m.return_pct.toFixed(2)+'%',m.return_pct>=0?'positive':'negative')+metric('Max drawdown',m.max_drawdown_pct.toFixed(2)+'%')+metric('Win rate',m.win_rate_pct.toFixed(1)+'%')+metric('Trades',m.trade_count)+metric('Costs',fmt(m.costs))+metric('OOS net P&amp;L',fmt(o.net_pnl),o.net_pnl>=0?'positive':'negative')+metric('OOS return',o.return_pct.toFixed(2)+'%',o.return_pct>=0?'positive':'negative')+metric('Exposure',m.exposure_pct.toFixed(1)+'%');$('trades').innerHTML=data.trades.map((t,i)=>`<tr><td>${i+1}</td><td>${escapeHtml(t.entry_time)}</td><td>${escapeHtml(t.exit_time)}</td><td>${fmt(t.gross_pnl)}</td><td>${fmt(t.costs)}</td><td class="${t.net_pnl>=0?'positive':'negative'}">${fmt(t.net_pnl)}</td></tr>`).join('')||'<tr><td colspan="6">No completed trades in this dataset.</td></tr>';$('warnings').textContent=data.warnings.join(' ');}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
$('run').addEventListener('click',async()=>{const button=$('run');$('status').textContent='';button.disabled=true;button.textContent='Running…';try{const payload={instrument:$('instrument').value,timeframe:$('timeframe').value,fast_period:Number($('fast').value),slow_period:Number($('slow').value),initial_capital:Number($('capital').value),quantity:Number($('quantity').value),fee_rate:Number($('fee').value)/100,slippage_rate:Number($('slippage').value)/100,bars:parseCSV($('csv').value)};const response=await fetch('/api/backtest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(data.error||'Backtest failed.');render(data);}catch(e){$('status').textContent=e.message;}finally{button.disabled=false;button.textContent='Run paper backtest';}});
</script>
</body></html>'''


def _json_metrics(metrics):
    value = metrics.__dict__.copy()
    if not isfinite(value["profit_factor"] if value["profit_factor"] is not None else 0):
        value["profit_factor"] = None
    return value


def _run(payload: dict) -> dict:
    allowed = {"instrument", "timeframe", "fast_period", "slow_period", "initial_capital",
               "quantity", "fee_rate", "slippage_rate", "bars"}
    if set(payload) != allowed:
        raise ValueError("Request must include exactly the documented strategy fields and bars.")
    raw_bars = payload["bars"]
    if not isinstance(raw_bars, list) or len(raw_bars) > 100_000:
        raise ValueError("bars must be a list with no more than 100,000 rows")
    bars = tuple(Bar(datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                     float(row["open"]), float(row["high"]), float(row["low"]),
                     float(row["close"]), float(row["volume"])) for row in raw_bars)
    strategy = MovingAverageCross(payload["instrument"], payload["timeframe"],
                                  int(payload["fast_period"]), int(payload["slow_period"]),
                                  initial_capital=float(payload["initial_capital"]),
                                  quantity=float(payload["quantity"]), fee_rate=float(payload["fee_rate"]),
                                  slippage_rate=float(payload["slippage_rate"]))
    result = run_backtest(bars, strategy, "user-uploaded-unversioned")
    return {"instrument": strategy.instrument, "bars": len(bars),
            "dataset_version": result.dataset_version, "split_index": result.split_index,
            "metrics": _json_metrics(result.metrics), "out_of_sample": _json_metrics(result.out_of_sample),
            "trades": [trade.__dict__ for trade in result.trades], "warnings": list(result.warnings)}


def make_handler():
    class Handler(BaseHTTPRequestHandler):
        server_version = "ScoutLocal/0.1"

        def log_message(self, fmt, *args):
            print("[scout] " + (fmt % args))

        def _respond(self, status, content_type, body):
            raw = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if urlparse(self.path).path == "/":
                self._respond(200, "text/html; charset=utf-8", PAGE)
            elif urlparse(self.path).path == "/health":
                self._respond(200, "application/json", '{"status":"ok","mode":"paper-research"}')
            else:
                self._respond(404, "application/json", '{"error":"not found"}')

        def do_POST(self):
            if urlparse(self.path).path != "/api/backtest":
                self._respond(404, "application/json", '{"error":"not found"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 15_000_000:
                    raise ValueError("request body is empty or exceeds 15 MB")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                result = _run(payload)
                self._respond(200, "application/json; charset=utf-8", json.dumps(result, allow_nan=False))
            except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError) as exc:
                self._respond(400, "application/json; charset=utf-8", json.dumps({"error": str(exc)}))
            except Exception:
                self._respond(500, "application/json; charset=utf-8", '{"error":"internal backtest error"}')
    return Handler


def main():
    host = os.environ.get("SCOUT_HOST", "127.0.0.1")
    port = int(os.environ.get("SCOUT_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), make_handler())
    print(f"Scout paper research UI: http://{host}:{port}")
    print("Press Ctrl+C to stop. The local server does not place broker orders.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Scout...")
    finally:
        server.server_close()
