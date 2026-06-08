#!/usr/bin/env python3
"""
Daily Trade Analysis Report — Gold, Silver & Indian Equities (Swing Trade)
Fetches real-time market data, generates a comprehensive HTML report, and emails it.
Designed to run via GitHub Actions on a daily cron schedule.
"""

import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

import yfinance as yf

# ── Configuration ──────────────────────────────────────────────────────────

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
TO_EMAILS = [e.strip() for e in os.environ.get("TO_EMAILS", "").split(",") if e.strip()]
CC_EMAILS = [e.strip() for e in os.environ.get("CC_EMAILS", "").split(",") if e.strip()]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

TODAY = datetime.now()
DATE_STR = TODAY.strftime("%B %d, %Y")


# ── Data Fetching ──────────────────────────────────────────────────────────

def fetch_data(symbol, period="1mo"):
    try:
        tk = yf.Ticker(symbol)
        hist = tk.history(period=period)
        if hist.empty:
            return None

        current = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else current
        change_pct = ((current - prev_close) / prev_close) * 100

        high_1m = hist["High"].max()
        low_1m = hist["Low"].min()
        high_1w = hist["High"].iloc[-5:].max() if len(hist) >= 5 else high_1m
        low_1w = hist["Low"].iloc[-5:].min() if len(hist) >= 5 else low_1m

        sma_20 = hist["Close"].rolling(20).mean().iloc[-1] if len(hist) >= 20 else None
        sma_10 = hist["Close"].rolling(10).mean().iloc[-1] if len(hist) >= 10 else None
        sma_5 = hist["Close"].rolling(5).mean().iloc[-1] if len(hist) >= 5 else None

        delta = hist["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1] if len(hist) >= 15 else None

        vol_avg = hist["Volume"].mean()
        vol_latest = hist["Volume"].iloc[-1]

        return {
            "price": round(float(current), 2),
            "prev_close": round(float(prev_close), 2),
            "change_pct": round(float(change_pct), 2),
            "high_1m": round(float(high_1m), 2),
            "low_1m": round(float(low_1m), 2),
            "high_1w": round(float(high_1w), 2),
            "low_1w": round(float(low_1w), 2),
            "sma_20": round(float(sma_20), 2) if sma_20 is not None else None,
            "sma_10": round(float(sma_10), 2) if sma_10 is not None else None,
            "sma_5": round(float(sma_5), 2) if sma_5 is not None else None,
            "rsi": round(float(rsi), 2) if rsi is not None else None,
            "vol_avg": int(vol_avg) if vol_avg else None,
            "vol_latest": int(vol_latest) if vol_latest else None,
        }
    except Exception as e:
        print(f"  Warning: {symbol}: {e}")
        return None


# ── Analysis Logic ─────────────────────────────────────────────────────────

def analyze_rsi(rsi):
    if rsi is None:
        return "N/A", "#666"
    if rsi > 70:
        return "Overbought", "#c62828"
    if rsi > 60:
        return "Bullish", "#2e7d32"
    if rsi > 40:
        return "Neutral", "#f57f17"
    if rsi > 30:
        return "Bearish", "#e65100"
    return "Oversold", "#c62828"


def get_trend(data):
    if data is None:
        return "N/A", "#666"
    price = data["price"]
    sma_20 = data.get("sma_20")
    sma_10 = data.get("sma_10")
    if sma_20 and sma_10:
        if price > sma_10 > sma_20:
            return "Strong Uptrend", "#2e7d32"
        if price > sma_20:
            return "Uptrend", "#43a047"
        if price < sma_10 < sma_20:
            return "Strong Downtrend", "#c62828"
        if price < sma_20:
            return "Downtrend", "#e53935"
    return "Sideways", "#f57f17"


def generate_verdict(data, asset_type="metal"):
    if data is None:
        return "WAIT", "Insufficient data.", "#f57f17"

    rsi = data.get("rsi")
    change = data.get("change_pct", 0)
    trend, _ = get_trend(data)

    if asset_type == "metal":
        if rsi and rsi < 30:
            return "BUY ON DIP", f"RSI at {rsi} — oversold. Look for support confirmation.", "#2e7d32"
        if rsi and rsi > 70:
            return "BOOK PROFITS", f"RSI at {rsi} — overbought. Consider partial profit-taking.", "#c62828"
        if "Downtrend" in trend and change < -1:
            return "WAIT", f"{trend} with {change}% change. Wait for reversal confirmation.", "#f57f17"
        if "Uptrend" in trend and rsi and 40 < rsi < 65:
            return "BUY", f"{trend} with healthy RSI at {rsi}. Good entry zone.", "#2e7d32"
        return "HOLD / WATCH", f"Mixed signals. RSI: {rsi}, Trend: {trend}.", "#f57f17"

    if asset_type == "stock":
        if rsi and rsi < 35 and "Downtrend" not in trend:
            return "BUY", f"RSI oversold at {rsi} without downtrend — potential reversal.", "#2e7d32"
        if rsi and rsi < 30:
            return "BUY ON DIP", f"RSI deeply oversold at {rsi}. Accumulate near support.", "#2e7d32"
        if rsi and rsi > 70:
            return "BOOK PROFITS", f"RSI overbought at {rsi}. Trail your stop-loss.", "#c62828"
        if "Strong Uptrend" in trend and rsi and 50 < rsi < 68:
            return "BUY", f"Strong uptrend, RSI at {rsi}. Momentum favours longs.", "#2e7d32"
        if "Uptrend" in trend:
            return "BUY ON DIP", f"Uptrend intact. Look for pullbacks to SMA for entry.", "#2e7d32"
        if "Downtrend" in trend:
            return "AVOID", f"Downtrend active. Wait for reversal.", "#616161"
        return "WATCH", f"Sideways. Wait for breakout direction.", "#f57f17"

    return "WATCH", "Analyzing...", "#f57f17"


# ── HTML Helpers ───────────────────────────────────────────────────────────

def fp(val, prefix="$", decimals=2):
    if val is None:
        return "N/A"
    return f"{prefix}{val:,.{decimals}f}"


def fc(val):
    if val is None:
        return "N/A"
    color = "#2e7d32" if val >= 0 else "#c62828"
    arrow = "&#9650;" if val >= 0 else "&#9660;"
    return f'<span style="color:{color};font-weight:bold;">{arrow} {val:+.2f}%</span>'


def tag(action, color):
    return f'<span style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold;color:white;background:{color};">{action}</span>'


# ── Report Sections ────────────────────────────────────────────────────────

def metal_section(name, emoji, data, prefix="$"):
    if data is None:
        return f"<h2>{emoji} {name} &mdash; Data Unavailable</h2><p>Could not fetch live data.</p>"

    verdict, reasoning, vc = generate_verdict(data, "metal")
    rsi_label, rsi_color = analyze_rsi(data.get("rsi"))
    trend, trend_color = get_trend(data)

    return f"""
    <h2>{emoji} {name.upper()} &mdash; Daily Analysis</h2>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin:10px 0;">
        <span class="pb">Price: {fp(data['price'], prefix)}</span>
        <span class="pb">Prev Close: {fp(data['prev_close'], prefix)}</span>
        <span class="pb">Change: {fc(data['change_pct'])}</span>
    </div>
    <table>
        <tr><th>Indicator</th><th>Value</th><th>Signal</th></tr>
        <tr><td>RSI (14)</td><td>{data.get('rsi', 'N/A')}</td><td><span style="color:{rsi_color};font-weight:bold;">{rsi_label}</span></td></tr>
        <tr><td>SMA-10</td><td>{fp(data.get('sma_10'), prefix)}</td><td>{'Price Above' if data['price'] > (data.get('sma_10') or 0) else 'Price Below'}</td></tr>
        <tr><td>SMA-20</td><td>{fp(data.get('sma_20'), prefix)}</td><td>{'Price Above' if data['price'] > (data.get('sma_20') or 0) else 'Price Below'}</td></tr>
        <tr><td>Trend</td><td colspan="2"><span style="color:{trend_color};font-weight:bold;">{trend}</span></td></tr>
        <tr><td>1-Month High</td><td colspan="2">{fp(data['high_1m'], prefix)}</td></tr>
        <tr><td>1-Month Low</td><td colspan="2">{fp(data['low_1m'], prefix)}</td></tr>
    </table>
    <div class="verdict" style="border-left-color:{vc};">
        <strong>{tag(verdict, vc)} &nbsp; Today's Verdict</strong><br/><br/>
        {reasoning}<br/><br/>
        <strong>Key levels:</strong> Support at {fp(data['low_1m'], prefix)} | Resistance at {fp(data['high_1m'], prefix)}
    </div>
    """


def stock_row(name, symbol, data):
    if data is None:
        return f"<tr><td><strong>{name}</strong></td><td colspan='7'>Data unavailable</td></tr>"

    verdict, reasoning, vc = generate_verdict(data, "stock")
    rsi_label, rsi_color = analyze_rsi(data.get("rsi"))

    vol_note = ""
    if data.get("vol_latest") and data.get("vol_avg") and data["vol_avg"] > 0:
        vr = data["vol_latest"] / data["vol_avg"]
        if vr > 1.5:
            vol_note = ' <span style="color:#2e7d32;font-size:10px;">HIGH VOL</span>'
        elif vr < 0.5:
            vol_note = ' <span style="color:#c62828;font-size:10px;">LOW VOL</span>'

    return f"""<tr>
        <td><strong>{name}</strong><br/><span style="color:#888;font-size:11px;">{symbol}</span></td>
        <td>&#8377;{data['price']:,.0f}</td>
        <td>{fc(data['change_pct'])}</td>
        <td><span style="color:{rsi_color};">{data.get('rsi', 'N/A')}</span></td>
        <td>&#8377;{data.get('sma_20', 0):,.0f}</td>
        <td>&#8377;{data['low_1w']:,.0f} &ndash; &#8377;{data['high_1w']:,.0f}</td>
        <td>{tag(verdict, vc)}</td>
        <td style="font-size:11px;">{reasoning}{vol_note}</td>
    </tr>"""


# ── Full Report ────────────────────────────────────────────────────────────

def build_report(metals, indices, stocks):
    nifty = indices.get("nifty50")
    sensex = indices.get("sensex")
    banknifty = indices.get("banknifty")

    nv, nr, nc = generate_verdict(nifty, "stock")

    idx_rows = ""
    for label, key in [("Nifty 50", "nifty50"), ("Sensex", "sensex"), ("Bank Nifty", "banknifty")]:
        d = indices.get(key)
        if d:
            idx_rows += f"<tr><td><strong>{label}</strong></td><td>{d['price']:,.0f}</td><td>{fc(d['change_pct'])}</td></tr>"
        else:
            idx_rows += f"<tr><td><strong>{label}</strong></td><td colspan='2'>N/A</td></tr>"

    stock_rows = "\n".join(stock_row(n, s, d) for n, s, d in stocks)

    gold_summary = metals.get("gold")
    silver_summary = metals.get("silver")

    def summary_row(name, data, prefix="$"):
        if data is None:
            return f"<tr><td>{name}</td><td>N/A</td><td>N/A</td></tr>"
        v, r, c = generate_verdict(data, "metal")
        return f"<tr><td><strong>{name}</strong></td><td>{tag(v, c)}</td><td>Support: {fp(data['low_1m'], prefix)} | Resistance: {fp(data['high_1m'], prefix)}</td></tr>"

    return f"""<html><head><style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1a1a1a; line-height: 1.6; max-width: 850px; margin: 0 auto; padding: 20px; }}
    h1 {{ color: #1a237e; border-bottom: 3px solid #c5a028; padding-bottom: 10px; font-size: 22px; }}
    h2 {{ color: #c5a028; font-size: 18px; margin-top: 30px; border-left: 4px solid #c5a028; padding-left: 12px; }}
    h3 {{ color: #333; font-size: 15px; margin-top: 20px; }}
    .verdict {{ background: #f5f5f5; border-left: 5px solid #1a237e; padding: 12px 16px; margin: 15px 0; border-radius: 4px; }}
    .pb {{ background: #e8eaf6; padding: 8px 14px; border-radius: 6px; display: inline-block; margin: 4px; font-weight: bold; font-size: 13px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
    th {{ background: #1a237e; color: white; padding: 8px 12px; text-align: left; font-size: 12px; }}
    td {{ padding: 7px 12px; border-bottom: 1px solid #e0e0e0; font-size: 12px; }}
    tr:nth-child(even) {{ background: #f9f9f9; }}
    .disc {{ font-size: 11px; color: #777; margin-top: 40px; border-top: 1px solid #ddd; padding-top: 15px; }}
    hr.div {{ border: none; border-top: 2px dashed #e0e0e0; margin: 35px 0; }}
    </style></head><body>

    <h1>&#128202; Daily Trade Analysis Report &mdash; {DATE_STR}</h1>
    <p style="color:#555;font-size:13px;">Gold, Silver &amp; Indian Equities (Swing Trade) | Generated {TODAY.strftime("%I:%M %p")} UTC</p>
    <hr style="border:1px solid #1a237e;">

    {metal_section("Gold", "&#129351;", metals.get("gold"))}
    <hr class="div">
    {metal_section("Silver", "&#129352;", metals.get("silver"))}
    <hr class="div">

    <h2>&#127470;&#127475; INDIAN EQUITIES &mdash; Swing Trade Analysis</h2>
    <h3>Market Snapshot</h3>
    <table><tr><th>Index</th><th>Level</th><th>Change</th></tr>{idx_rows}</table>

    <h3>Swing Trade Stock Scanner</h3>
    <table>
        <tr><th>Stock</th><th>Price</th><th>Change</th><th>RSI</th><th>SMA-20</th><th>1W Range</th><th>Action</th><th>Reasoning</th></tr>
        {stock_rows}
    </table>

    <div class="verdict" style="border-left-color:{nc};">
        <strong>{tag(nv, nc)} &nbsp; Market Verdict</strong><br/><br/>
        {nr}<br/><br/>
        <strong>Strategy:</strong> Focus on RSI oversold + uptrend stocks (best risk/reward). Avoid stocks in strong downtrends. Keep position sizes moderate until direction clears.
    </div>

    <hr class="div">
    <h2>&#128203; Quick Reference</h2>
    <table>
        <tr><th>Asset</th><th>Action</th><th>Key Levels</th></tr>
        {summary_row("Gold", gold_summary)}
        {summary_row("Silver", silver_summary)}
    </table>

    <p class="disc">
    <strong>DISCLAIMER:</strong> This report is for informational and educational purposes only. It does NOT constitute investment advice. All investments carry risk. Always consult a qualified financial advisor. Not SEBI-registered.<br/><br/>
    <strong>Data:</strong> Yahoo Finance via yfinance. Technical indicators from 1-month historical data.
    </p>
    </body></html>"""


# ── Email ──────────────────────────────────────────────────────────────────

def send_email(html):
    if not SENDER_EMAIL or not APP_PASSWORD or not TO_EMAILS:
        print("ERROR: Missing SENDER_EMAIL, APP_PASSWORD, or TO_EMAILS")
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Trade Analysis Report — {DATE_STR} | Gold, Silver & Indian Equities"
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(TO_EMAILS)
    if CC_EMAILS:
        msg["Cc"] = ", ".join(CC_EMAILS)

    msg.attach(MIMEText(f"Daily Trade Report for {DATE_STR}. View in HTML.", "plain"))
    msg.attach(MIMEText(html, "html"))

    all_recipients = TO_EMAILS + CC_EMAILS
    print(f"Sending to: {', '.join(all_recipients)}")

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, all_recipients, msg.as_string())

    print("Email sent successfully!")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print(f"=== Daily Trade Report — {DATE_STR} ===\n")

    metal_tickers = {"gold": "GC=F", "silver": "SI=F"}
    index_tickers = {"nifty50": "^NSEI", "sensex": "^BSESN", "banknifty": "^NSEBANK"}
    stock_tickers = [
        ("ICICI Bank", "ICICIBANK.NS"),
        ("SBI", "SBIN.NS"),
        ("HDFC Bank", "HDFCBANK.NS"),
        ("L&T", "LT.NS"),
        ("REC Ltd", "RECLTD.NS"),
        ("Reliance", "RELIANCE.NS"),
        ("Tata Motors", "TATAMOTORS.NS"),
        ("Bharti Airtel", "BHARTIARTL.NS"),
        ("Infosys", "INFY.NS"),
    ]

    print("Fetching precious metals...")
    metals = {}
    for name, sym in metal_tickers.items():
        print(f"  {sym}...", end=" ")
        metals[name] = fetch_data(sym)
        print("OK" if metals[name] else "FAILED")

    print("Fetching indices...")
    indices = {}
    for name, sym in index_tickers.items():
        print(f"  {sym}...", end=" ")
        indices[name] = fetch_data(sym)
        print("OK" if indices[name] else "FAILED")

    print("Fetching stocks...")
    stocks = []
    for name, sym in stock_tickers:
        print(f"  {sym}...", end=" ")
        d = fetch_data(sym)
        stocks.append((name, sym, d))
        print("OK" if d else "FAILED")

    print("\nBuilding report...")
    html = build_report(metals, indices, stocks)

    print("Sending email...")
    send_email(html)
    print("\nDone!")


if __name__ == "__main__":
    main()
