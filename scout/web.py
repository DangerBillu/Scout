"""Local browser interface for trying Scout's deterministic paper backtest."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from math import isfinite
from urllib.parse import parse_qs, urlparse

from .backtest import run_backtest
from .data import Bar, INSTRUMENT_METADATA
from .strategy import MovingAverageCross
from .config import ModelConfig
from .discovery import DiscoveryConfig, discover
from .automation import AutomationJob
from .ingestion import CsvSourceAdapter
from .idea_checker import check_idea
from .market import YahooFinanceProvider, market_provider_status
from .portfolio import PaperPortfolio
from .agent import reply as agent_reply
from .knowledge import KnowledgeStore
from .persistence import Store
from .recommendations import Recommendation, RecommendationState


KNOWLEDGE = KnowledgeStore()
RECOMMENDATIONS: dict[str, Recommendation] = {}
AUTOMATIONS: dict[str, AutomationJob] = {}
STORE: Store | None = None
PAPER_PORTFOLIO = PaperPortfolio("local-paper", float(os.getenv("SCOUT_PAPER_CAPITAL", "100000")))
PAPER_ORDERS: list[dict[str, object]] = []


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
    .nav{display:flex;gap:18px;align-items:center}.nav a{color:var(--muted);text-decoration:none;font-size:13px}.nav a:hover{color:var(--mint)}
    .terminal{margin:0 0 20px;background:linear-gradient(135deg,#0e1b15,#0b1110);border:1px solid #244c3c;border-radius:14px;padding:18px}.terminal-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.terminal-grid{display:grid;grid-template-columns:1.35fr .65fr;gap:14px;margin-top:15px}.quote-card,.order-card{background:#080d0a;border:1px solid var(--line);border-radius:11px;padding:16px}.quote-symbol{font-size:13px;color:var(--muted)}.quote-price{font-size:34px;font-weight:750;letter-spacing:-.03em;margin:4px 0}.live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#68766e;margin-right:6px}.live-dot.on{background:var(--mint);box-shadow:0 0 8px var(--mint)}.chart{width:100%;height:150px;display:block;margin-top:10px}.mini{font-size:12px;color:var(--muted)}.order-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.buy{background:var(--mint)!important}.sell{background:var(--coral)!important;color:#190504!important}.outline{background:transparent!important;color:var(--mint)!important;border:1px solid #2f7b5a!important}.idea{margin:20px 0}.idea-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}.idea-result{margin-top:12px;padding:10px;border-radius:8px;background:#0a100d;color:var(--muted);font-size:13px;white-space:pre-wrap}.verdict{font-weight:700;color:var(--mint)}.chat{position:fixed;right:22px;bottom:22px;width:min(390px,calc(100vw - 44px));background:#0d1410;border:1px solid #316a50;border-radius:14px;box-shadow:0 16px 45px #0009;z-index:5;display:none}.chat.open{display:block}.chat-head{padding:14px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.chat-body{padding:14px}.chat-log{height:190px;overflow:auto;font-size:13px;color:var(--muted);white-space:pre-wrap}.chat-actions{display:flex;gap:8px}.chat-actions input{flex:1}.icon-button{background:transparent;border:1px solid var(--line);color:var(--muted);border-radius:7px;padding:6px 9px;cursor:pointer}
    label{display:block;font-size:13px;color:#d8e0db;margin:12px 0 6px}input,select,textarea{width:100%;border:1px solid #34443c;background:#090c0a;color:white;border-radius:8px;padding:10px 11px;font:inherit}textarea{min-height:260px;resize:vertical;font:12px/1.45 ui-monospace,Consolas,monospace}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.hint{font-size:12px;color:var(--muted);margin:7px 0}.button{margin-top:18px;width:100%;border:0;background:var(--mint);color:#04110b;border-radius:8px;padding:12px;font-weight:700;font-size:15px;cursor:pointer}.button:disabled{opacity:.6;cursor:wait}
    .empty{min-height:300px;display:grid;place-items:center;text-align:center;color:var(--muted)}.status{margin-top:12px;color:var(--coral);font-size:13px;white-space:pre-wrap}.results{display:none}.metric-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{border:1px solid var(--line);padding:13px;border-radius:10px}.metric small{display:block;color:var(--muted)}.metric strong{font-size:20px;display:block;margin-top:4px}.positive{color:var(--mint)}.negative{color:var(--coral)}
    .table-wrap{overflow:auto;margin-top:20px}table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}th,td{text-align:right;padding:9px;border-bottom:1px solid var(--line)}th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-weight:500}.warning{margin-top:18px;border-left:3px solid #a8ed16;padding:9px 12px;color:var(--muted);font-size:12px}.pill{display:inline-block;border:1px solid var(--line);border-radius:20px;padding:3px 9px;margin:0 5px 8px 0;font-size:11px;color:var(--muted)}
    @media(max-width:800px){.layout,.terminal-grid{grid-template-columns:1fr}.idea-grid{grid-template-columns:1fr}.intro h1{font-size:25px}.metric-grid{grid-template-columns:repeat(2,1fr)}header{padding:18px 24px}.nav{display:none}}
  </style>
</head>
<body>
  <header><div class="brand">SCOUT<span>.</span></div><nav class="nav"><a href="#terminal">Terminal</a><a href="#idea">Idea Checker</a><a href="#backtest">Backtest</a></nav><div class="tag">PAPER MODE · NO BROKER ORDERS</div></header>
  <main>
    <section id="terminal" class="terminal">
      <div class="terminal-head"><div><span class="live-dot" id="liveDot"></span><span id="liveState" class="mini">Live quote not connected</span></div><div class="row" style="min-width:360px"><select id="liveInstrument"><option value="NSE:NIFTY50">NIFTY 50 · NSE</option><option value="NSE:NIFTYBANK">NIFTY BANK · NSE</option></select><select id="liveTimeframe"><option value="5m">5 minute</option><option value="15m">15 minute</option><option value="1h">1 hour</option></select><button id="refreshMarket" class="icon-button">Connect quote</button></div></div>
      <div class="terminal-grid"><div class="quote-card"><div class="quote-symbol" id="liveSymbol">NIFTY 50 · waiting for provider</div><div class="quote-price" id="livePrice">—</div><div id="liveMeta" class="mini">Configure a licensed market-data API key to see live quotes.</div><canvas id="priceChart" class="chart" width="760" height="150"></canvas></div>
        <div class="order-card"><h2 style="margin-bottom:8px">Paper order</h2><div class="mini">Orders use the latest validated quote and never reach a broker.</div><label for="orderQty">Quantity</label><input id="orderQty" type="number" min="1" step="1" value="1"><div class="order-grid"><button class="button buy" id="buyOrder">Buy</button><button class="button sell" id="sellOrder">Sell</button></div><div id="orderStatus" class="status"></div></div></div>
    </section>
    <section class="intro"><h1>Learn, test, then paper trade</h1><div class="muted">Scout explains the setup, checks the risk, and keeps every fill simulated for beginner intraday research.</div></section>
    <section id="idea" class="card idea"><h2>Idea Checker</h2><div class="muted mini">Describe a simple setup. Scout checks that it has bounded risk before you backtest it.</div><div class="idea-grid"><div><label for="entryRule">Entry rule</label><input id="entryRule" placeholder="Fast average crosses above slow"></div><div><label for="exitRule">Exit rule</label><input id="exitRule" placeholder="Close below slow average"></div><div><label for="riskTrade">Risk per trade (%)</label><input id="riskTrade" type="number" min="0.1" max="5" step="0.1" value="1"></div></div><div class="row"><div><label for="stopPct">Stop-loss (%)</label><input id="stopPct" type="number" min="0.1" step="0.1" value="0.8"></div><div><label for="targetPct">Take-profit (%)</label><input id="targetPct" type="number" min="0.1" step="0.1" value="1.2"></div></div><button class="button outline" id="checkIdea">Check this idea</button><div id="ideaResult" class="idea-result">No idea checked yet.</div></section>
    <div id="backtest" class="layout">
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
    <p class="hint" style="margin-top:20px">Research only. Simulated fills do not guarantee real execution. Scout does not place orders. Live quotes require a configured licensed provider and are never replaced with synthetic values.</p>
  </main>
  <aside id="chat" class="chat"><div class="chat-head"><strong>Scout Guide</strong><button class="icon-button" id="closeChat">Close</button></div><div class="chat-body"><div id="chatLog" class="chat-log">Ask about the setup, risk, or how to read the screen. Your message stays local in this build.</div><div class="chat-actions"><input id="chatInput" placeholder="Ask Scout…"><button class="icon-button" id="voice" title="Voice command">🎙</button><button class="icon-button" id="sendChat">Send</button></div><div class="mini" style="margin-top:8px">Ctrl+Space opens this guide. Voice capture needs browser speech support.</div></div></aside>
<script>
const $=id=>document.getElementById(id); const fmt=n=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(n);
function openChat(){ $('chat').classList.add('open');$('chatInput').focus(); } function closeChat(){ $('chat').classList.remove('open'); }
async function sendChat(){const input=$('chatInput'),message=input.value.trim();if(!message)return;const log=$('chatLog');log.textContent+='\n\nYou: '+message;input.value='';try{const response=await fetch('/api/agent/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});const data=await response.json();log.textContent+='\n\nScout: '+data.text+(data.available?'':'\n\n[AI unavailable; deterministic tools remain available.]');log.scrollTop=log.scrollHeight;}catch(error){log.textContent+='\n\nScout: Chat request failed locally: '+error.message;}}
$('sendChat').addEventListener('click',sendChat);$('chatInput').addEventListener('keydown',event=>{if(event.key==='Enter')sendChat();});$('closeChat').addEventListener('click',closeChat);document.addEventListener('keydown',event=>{if(event.ctrlKey&&event.code==='Space'){event.preventDefault();openChat();}});
$('voice').addEventListener('click',()=>{$('chatLog').textContent='Voice commands are not enabled in this build. Browser speech recognition may send audio to a third-party speech service; configure and approve a specific provider before enabling it.';});
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
$('checkIdea').addEventListener('click',async()=>{const result=$('ideaResult');try{const response=await fetch('/api/ideas/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:$('liveInstrument').value,timeframe:$('liveTimeframe').value,entry_rule:$('entryRule').value,exit_rule:$('exitRule').value,stop_loss_pct:Number($('stopPct').value),take_profit_pct:Number($('targetPct').value),risk_per_trade_pct:Number($('riskTrade').value)})});const data=await response.json();result.innerHTML=`<span class="verdict">${escapeHtml(data.verdict)}</span>\n${escapeHtml(data.summary)}\n\n${data.warnings.length?'Warnings: '+data.warnings.join(' '):'No warnings.'}`;}catch(error){result.textContent=error.message;}});
async function paperOrder(side){const status=$('orderStatus');status.textContent='';try{const response=await fetch('/api/paper/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:$('liveInstrument').value,timeframe:$('liveTimeframe').value,side,quantity:Number($('orderQty').value)})});const data=await response.json();if(!response.ok)throw Error(data.error||'Paper order rejected');status.textContent=`${data.order.side} ${data.order.quantity} @ ${fmt(data.order.price)} recorded in PAPER mode.`;}catch(error){status.textContent=error.message;}}
$('buyOrder').addEventListener('click',()=>paperOrder('BUY'));$('sellOrder').addEventListener('click',()=>paperOrder('SELL'));
async function refreshMarket(){const instrument=$('liveInstrument').value,timeframe=$('liveTimeframe').value;const button=$('refreshMarket');button.disabled=true;button.textContent='Loading…';try{const [quoteResponse,candleResponse]=await Promise.all([fetch(`/api/market/quote?instrument=${encodeURIComponent(instrument)}&timeframe=${timeframe}`),fetch(`/api/market/candles?instrument=${encodeURIComponent(instrument)}&timeframe=${timeframe}`)]);const quote=await quoteResponse.json();if(!quoteResponse.ok)throw Error(quote.error||'Live provider unavailable');const candles=await candleResponse.json();$('liveDot').classList.add('on');$('liveState').textContent='Live quote connected · '+quote.provider;$('liveSymbol').textContent=quote.symbol+' · '+instrument;$('livePrice').textContent=fmt(quote.close);$('liveMeta').textContent=quote.timestamp+' · '+(quote.delayed?'delayed':'provider timestamp')+' · '+quote.provenance;const canvas=$('priceChart'),ctx=canvas.getContext('2d'),bars=candles.bars||[],values=bars.map(x=>Number(x.close));ctx.clearRect(0,0,canvas.width,canvas.height);if(values.length>1){const lo=Math.min(...values),hi=Math.max(...values);ctx.strokeStyle='#36E6A0';ctx.lineWidth=2;ctx.beginPath();values.forEach((value,index)=>{const x=8+(canvas.width-16)*index/(values.length-1),y=canvas.height-8-(value-lo)/(hi-lo||1)*(canvas.height-16);index?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}}catch(error){$('liveDot').classList.remove('on');$('liveState').textContent='Live quote unavailable';$('liveMeta').textContent=error.message+' No synthetic value was inserted.';}finally{button.disabled=false;button.textContent='Connect quote';}}
$('refreshMarket').addEventListener('click',refreshMarket);$('liveInstrument').addEventListener('change',()=>{$('liveState').textContent='Selection changed · connect quote to refresh';});$('liveTimeframe').addEventListener('change',()=>{$('liveState').textContent='Selection changed · connect quote to refresh';});
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


def _json_request(handler: BaseHTTPRequestHandler, maximum: int = 15_000_000) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > maximum:
        raise ValueError("request body is empty or exceeds the size limit")
    payload = json.loads(handler.rfile.read(length))
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def _discovery(payload: dict) -> dict:
    # Discovery deliberately accepts the same explicit bars/strategy primitives
    # as the backtest endpoint. It never evaluates generated Python.
    bars = tuple(Bar(datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                     float(row["open"]), float(row["high"]), float(row["low"]),
                     float(row["close"]), float(row["volume"])) for row in payload.get("bars", []))
    result = discover(bars, payload["instrument"], payload.get("timeframe", "1d"),
                      float(payload.get("initial_capital", 100_000)), payload.get("dataset_version", "uploaded"),
                      DiscoveryConfig(max_candidates=int(payload.get("max_candidates", 10))))
    return {"status": result.status, "candidates": [{"fast_period": candidate.strategy.fast_period,
            "slow_period": candidate.strategy.slow_period, "metrics": _json_metrics(candidate.metrics),
            "out_of_sample": _json_metrics(candidate.out_of_sample)} for candidate in result.candidates],
            "rejected": list(result.rejected), "configuration": result.configuration.__dict__}


def _quality(payload: dict) -> dict:
    bars, dataset, report = CsvSourceAdapter().read(payload.get("csv", ""),
        instrument=payload.get("instrument", "NSE:NIFTY50"), timeframe=payload.get("timeframe", "1d"),
        version=payload.get("version", "uploaded"))
    return {"dataset": dataset.__dict__, "quality": report.__dict__, "bar_count": len(bars)}


def _store() -> Store:
    global STORE
    if STORE is None:
        STORE = Store(os.environ.get("SCOUT_DB_PATH", "scout.db"))
    return STORE


def _recommendation_payload(recommendation: Recommendation) -> dict:
    return {"recommendation_id": recommendation.recommendation_id, "hypothesis": recommendation.hypothesis,
            "baseline": recommendation.baseline, "candidate": recommendation.candidate,
            "dataset_version": recommendation.dataset_version, "strategy_version": recommendation.strategy_version,
            "evidence": recommendation.evidence, "state": recommendation.state.value,
            "audit": [event.__dict__ for event in recommendation.audit]}


def _get_recommendation(recommendation_id: str | None) -> Recommendation | None:
    if not recommendation_id:
        return None
    if recommendation_id in RECOMMENDATIONS:
        return RECOMMENDATIONS[recommendation_id]
    payload = _store().get("recommendation", recommendation_id)
    if not payload:
        return None
    recommendation = Recommendation(payload["recommendation_id"], payload["hypothesis"], payload["baseline"],
                                    payload["candidate"], payload["dataset_version"], payload["strategy_version"],
                                    payload["evidence"], RecommendationState(payload.get("state", "HYPOTHESIS")))
    RECOMMENDATIONS[recommendation_id] = recommendation
    return recommendation


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
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._respond(200, "text/html; charset=utf-8", PAGE)
            elif parsed.path == "/health":
                self._respond(200, "application/json", json.dumps({"status": "ok", "mode": "paper-research",
                                                                      "live_trading": False}))
            elif parsed.path in {"/api/models/config", "/api/integrations/status"}:
                self._respond(200, "application/json", json.dumps({"model": ModelConfig.from_env().public(),
                                                                      "mcp": {"enabled": False, "status": "extension-point"},
                                                                      "live_trading": False}))
            elif parsed.path == "/api/data/instruments":
                self._respond(200, "application/json", json.dumps([metadata.__dict__ for metadata in INSTRUMENT_METADATA.values()]))
            elif parsed.path == "/api/market/status":
                self._respond(200, "application/json", json.dumps(market_provider_status()))
            elif parsed.path == "/api/market/quote":
                query = parse_qs(parsed.query)
                try:
                    quote = YahooFinanceProvider().latest(query.get("instrument", ["NSE:NIFTY50"])[0],
                                                        query.get("timeframe", ["5m"])[0])
                    self._respond(200, "application/json", json.dumps(quote.__dict__))
                except (RuntimeError, ValueError) as exc:
                    self._respond(503, "application/json", json.dumps({"error": str(exc), "live": False}))
            elif parsed.path == "/api/market/candles":
                query = parse_qs(parsed.query)
                try:
                    bars = YahooFinanceProvider().recent(query.get("instrument", ["NSE:NIFTY50"])[0],
                                                        query.get("timeframe", ["5m"])[0])
                    self._respond(200, "application/json", json.dumps({"live": True, "provider": "yahoo_finance",
                        "bars": [bar.__dict__ | {"timestamp": bar.timestamp.isoformat()} for bar in bars]}))
                except (RuntimeError, ValueError) as exc:
                    self._respond(503, "application/json", json.dumps({"error": str(exc), "live": False}))
            elif parsed.path == "/api/paper/portfolio":
                query = parse_qs(parsed.query)
                try:
                    instrument = query.get("instrument", ["NSE:NIFTY50"])[0]
                    quote = YahooFinanceProvider().latest(instrument, query.get("timeframe", ["5m"])[0])
                    snapshot = PAPER_PORTFOLIO.snapshot({instrument: quote.close})
                    self._respond(200, "application/json", json.dumps({"snapshot": snapshot.__dict__,
                        "positions": [position.__dict__ for position in snapshot.positions], "live": True,
                        "orders": PAPER_ORDERS}, default=str))
                except (RuntimeError, ValueError) as exc:
                    self._respond(503, "application/json", json.dumps({"error": str(exc), "live": False,
                                                                          "orders": PAPER_ORDERS}))
            elif parsed.path == "/api/knowledge/search":
                query = parse_qs(parsed.query).get("q", [""])[0]
                hits = KNOWLEDGE.search(query) if query else ()
                self._respond(200, "application/json", json.dumps({"hits": [hit.__dict__ for hit in hits],
                                                                      "source_grounded": bool(hits)}, default=str))
            elif parsed.path == "/api/recommendations":
                local = [{"id": item.recommendation_id, "state": item.state.value, "hypothesis": item.hypothesis}
                         for item in RECOMMENDATIONS.values()]
                persisted = [{"id": item.get("recommendation_id"), "state": item.get("state"),
                              "hypothesis": item.get("hypothesis")} for item in _store().list("recommendation")]
                seen = {item["id"] for item in local}
                self._respond(200, "application/json", json.dumps(local + [item for item in persisted if item["id"] not in seen]))
            elif parsed.path == "/api/automations":
                local = [job.__dict__ for job in AUTOMATIONS.values()]
                persisted = _store().list("automation")
                seen = {item["job_id"] for item in local}
                self._respond(200, "application/json", json.dumps(local + [item for item in persisted if item["job_id"] not in seen]))
            elif parsed.path == "/api/activity":
                self._respond(200, "application/json", json.dumps(list(_store().audit_history())))
            else:
                self._respond(404, "application/json", '{"error":"not found"}')

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in {"/api/backtest", "/api/discovery", "/api/data/validate", "/api/ideas/check",
                            "/api/agent/chat",
                            "/api/paper/orders",
                            "/api/recommendations", "/api/recommendations/transition", "/api/automations",
                            "/api/automations/run"}:
                self._respond(404, "application/json", '{"error":"not found"}')
                return
            try:
                payload = _json_request(self)
                if path == "/api/backtest":
                    result = _run(payload)
                elif path == "/api/discovery":
                    result = _discovery(payload)
                elif path == "/api/data/validate":
                    result = _quality(payload)
                elif path == "/api/ideas/check":
                    result = check_idea(instrument=payload.get("instrument", ""), timeframe=payload.get("timeframe", ""),
                                        entry_rule=payload.get("entry_rule", ""), exit_rule=payload.get("exit_rule", ""),
                                        stop_loss_pct=float(payload.get("stop_loss_pct", 0)),
                                        take_profit_pct=float(payload.get("take_profit_pct", 0)),
                                        risk_per_trade_pct=float(payload.get("risk_per_trade_pct", 0))).__dict__
                elif path == "/api/agent/chat":
                    result = agent_reply(payload.get("message", "")).__dict__
                elif path == "/api/paper/orders":
                    instrument = payload.get("instrument", "NSE:NIFTY50")
                    side = str(payload.get("side", "")).upper()
                    quantity = float(payload.get("quantity", 0))
                    if side not in {"BUY", "SELL"} or quantity <= 0:
                        raise ValueError("paper order requires side BUY/SELL and positive quantity")
                    quote = YahooFinanceProvider().latest(instrument, payload.get("timeframe", "5m"))
                    signed_quantity = quantity if side == "BUY" else -quantity
                    PAPER_PORTFOLIO.apply_paper_fill(instrument, signed_quantity, quote.close)
                    order = {"instrument": instrument, "side": side, "quantity": quantity,
                             "price": quote.close, "timestamp": quote.timestamp, "mode": "PAPER",
                             "provider": quote.provider}
                    PAPER_ORDERS.append(order)
                    result = {"order": order, "message": "Paper fill recorded. No broker order was sent."}
                elif path == "/api/recommendations/transition":
                    recommendation = _get_recommendation(payload.get("recommendation_id"))
                    if recommendation is None:
                        raise ValueError("recommendation not found")
                    recommendation.transition(RecommendationState(payload["state"]), payload["actor"], payload["reason"])
                    _store().put("recommendation", recommendation.recommendation_id,
                                 _recommendation_payload(recommendation), action="recommendation.transition",
                                 actor=payload["actor"])
                    result = {"id": recommendation.recommendation_id, "state": recommendation.state.value,
                              "audit": [event.__dict__ for event in recommendation.audit]}
                elif path == "/api/automations":
                    required = {"job_id", "name", "interval_seconds"}
                    if not required.issubset(payload):
                        raise ValueError("job_id, name, and interval_seconds are required")
                    if payload["job_id"] in AUTOMATIONS or _store().get("automation", payload["job_id"]):
                        raise ValueError("automation already exists")
                    job = AutomationJob(payload["job_id"], payload["name"], int(payload["interval_seconds"]))
                    AUTOMATIONS[job.job_id] = job
                    _store().put("automation", job.job_id, job.__dict__, action="automation.create", actor="system")
                    result = job.__dict__
                elif path == "/api/automations/run":
                    job = AUTOMATIONS.get(payload.get("job_id"))
                    if job is None:
                        raise ValueError("automation not found")
                    result = job.request_run(actor=payload.get("actor", ""))
                    _store().put("automation", job.job_id, job.__dict__, action="automation.run",
                                 actor=payload["actor"])
                else:
                    required = {"recommendation_id", "hypothesis", "baseline", "candidate",
                                "dataset_version", "strategy_version", "evidence"}
                    if set(payload) != required:
                        raise ValueError("recommendation payload is missing required evidence fields")
                    if payload["recommendation_id"] in RECOMMENDATIONS or _store().get("recommendation", payload["recommendation_id"]):
                        raise ValueError("recommendation already exists")
                    recommendation = Recommendation(payload["recommendation_id"], payload["hypothesis"],
                                                    payload["baseline"], payload["candidate"],
                                                    payload["dataset_version"], payload["strategy_version"],
                                                    payload["evidence"])
                    RECOMMENDATIONS[recommendation.recommendation_id] = recommendation
                    _store().put("recommendation", recommendation.recommendation_id,
                                 _recommendation_payload(recommendation), action="recommendation.create", actor="system")
                    result = {"id": recommendation.recommendation_id, "state": recommendation.state.value,
                              "message": "Recommendation recorded as HYPOTHESIS; explicit review is required."}
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
