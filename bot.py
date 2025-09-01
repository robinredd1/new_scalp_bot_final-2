import os, time, math, json, sys, requests
from datetime import datetime
from dateutil import tz
import pandas as pd

from config import (
    FINNHUB_API_KEY, PRICE_MIN, PRICE_MAX, MIN_PCT_CHANGE, MIN_REL_VOL,
    NEWS_LOOKBACK_MIN, SCAN_BATCH, SLEEP_SECONDS, PREPOST_PROGRESS,
    REGULAR_SESSION_START_ET, REGULAR_SESSION_END_ET, WATCHLIST
)

API = "https://finnhub.io/api/v1"
HEADERS = {"X-Finnhub-Token": FINNHUB_API_KEY}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
SYMBOLS_CACHE = os.path.join(DATA_DIR, "symbols_us.json")

def _et_now():
    return datetime.now(tz.gettz("America/New_York"))

def session_progress_et(now_et: datetime):
    start = datetime.combine(now_et.date(), datetime.strptime(REGULAR_SESSION_START_ET, "%H:%M").time(), tzinfo=now_et.tzinfo)
    end   = datetime.combine(now_et.date(), datetime.strptime(REGULAR_SESSION_END_ET,   "%H:%M").time(), tzinfo=now_et.tzinfo)
    if now_et < start:
        return 0.0
    if now_et > end:
        return 1.0
    total = (end - start).total_seconds()
    done = (now_et - start).total_seconds()
    return max(0.0, min(1.0, done / total))

def get_symbols_us():
    if os.path.exists(SYMBOLS_CACHE):
        with open(SYMBOLS_CACHE, "r") as f:
            return json.load(f)
    r = requests.get(f"{API}/stock/symbol", params={"exchange": "US"}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    symbols = [s for s in r.json() if s.get("type") in ("Common Stock","ETP","REIT") and s.get("symbol")]
    with open(SYMBOLS_CACHE, "w") as f:
        json.dump(symbols, f)
    return symbols

def get_quote(sym: str):
    r = requests.get(f"{API}/quote", params={"symbol": sym}, headers=HEADERS, timeout=10)
    if r.status_code != 200: return None
    return r.json()  # c,d,dp,h,l,o,pc

def get_metrics(sym: str):
    r = requests.get(f"{API}/stock/metric", params={"symbol": sym, "metric": "all"}, headers=HEADERS, timeout=15)
    if r.status_code != 200: return None
    m = r.json().get("metric", {})
    avg10 = m.get("10DayAverageTradingVolume") or m.get("10DayAvgVolume") or m.get("avgVolume10D")
    avg30 = m.get("30DayAverageTradingVolume") or m.get("30DayAvgVolume") or m.get("avgVolume30D")
    return {"avg10": avg10, "avg30": avg30}

def get_today_volume(sym: str):
    now = int(time.time())
    r = requests.get(f"{API}/stock/candle", params={"symbol": sym, "resolution": "1", "from": now - 60*60*10, "to": now}, headers=HEADERS, timeout=20)
    if r.status_code != 200: return None
    j = r.json()
    if j.get("s") != "ok": return None
    vols = j.get("v", [])
    return sum(vols) if vols else None

def has_fresh_news(sym: str, lookback_min: int):
    end = int(time.time())
    start = end - lookback_min*60
    r = requests.get(f"{API}/company-news", params={
        "symbol": sym,
        "from": datetime.utcfromtimestamp(start).strftime("%Y-%m-%d"),
        "to":   datetime.utcfromtimestamp(end).strftime("%Y-%m-%d")
    }, headers=HEADERS, timeout=15)
    if r.status_code != 200: 
        return (False, None)
    news = r.json()
    latest = None
    for n in news:
        ts = n.get("datetime") or n.get("time")
        if ts is None: 
            continue
        if isinstance(ts, (int, float)):
            t = int(ts)
        else:
            try:
                t = int(pd.Timestamp(ts).timestamp())
            except:
                continue
        if t >= start:
            headline = n.get("headline") or n.get("title")
            latest = (t, headline)
            break
    if latest:
        return (True, latest[1])
    return (False, None)

def scan_once(symbols):
    now_et = _et_now()
    prog = session_progress_et(now_et)
    if prog <= 0.0 or prog >= 1.0:
        prog = PREPOST_PROGRESS
    
    hits = []
    for sym in symbols:
        try:
            q = get_quote(sym)
            if not q: 
                continue
            price = q.get("c")
            pct = q.get("dp")
            if not price or price < PRICE_MIN or price > PRICE_MAX:
                continue
            if pct is None or pct < MIN_PCT_CHANGE:
                continue

            today_vol = get_today_volume(sym) or 0
            metrics = get_metrics(sym) or {}
            avg10 = metrics.get("avg10") or metrics.get("avg30") or 0
            denom = max(1.0, (avg10 or 1.0) * max(0.1, prog))
            rvol = today_vol / denom

            if rvol < MIN_REL_VOL:
                continue

            has_news, headline = has_fresh_news(sym, NEWS_LOOKBACK_MIN)
            if not has_news:
                continue

            hits.append({
                "symbol": sym, "price": price, "pct": pct, "rvol": rvol, "headline": headline or "(news)"
            })
        except Exception as e:
            print(f"[warn] {sym}: {e}", file=sys.stderr)
            continue
    return sorted(hits, key=lambda x: (-x["pct"], -x["rvol"]))

def print_hits(hits):
    ts = _et_now().strftime("%H:%M:%S")
    if not hits:
        print(f"[{ts}] No matches (2–20$, +10%, rVol≥5×, news last {NEWS_LOOKBACK_MIN}m).")
        return
    for h in hits:
        print(f"[{ts}] ✅ HIT {h['symbol']} ${h['price']:.2f} (+{h['pct']:.1f}%) rVol {h['rvol']:.1f}× | "{h['headline']}"")
        p = h['price']
        t1 = p * 1.05
        t2 = p * 1.10
        stop = p * 0.94
        print(f"         Buy@{p:.2f}  Target1@{t1:.2f}  Target2@{t2:.2f}  Stop@{stop:.2f}")

def main():
    if not FINNHUB_API_KEY:
        print("ERROR: Missing FINNHUB_API_KEY. Check config.py")
        sys.exit(1)

    # Load or fetch US symbols
    if os.path.exists(SYMBOLS_CACHE):
        with open(SYMBOLS_CACHE, "r") as f:
            all_syms = [s["symbol"] for s in json.load(f)]
    else:
        r = requests.get(f"{API}/stock/symbol", params={"exchange": "US"}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        syms = [s for s in r.json() if s.get("type") in ("Common Stock","ETP","REIT") and s.get("symbol")]
        with open(SYMBOLS_CACHE, "w") as f:
            json.dump(syms, f)
        all_syms = [s["symbol"] for s in syms]

    if WATCHLIST:
        base = [s for s in all_syms if s in WATCHLIST]
    else:
        base = [s for s in all_syms if "/" not in s and "-" not in s]

    print(f"Loaded {len(base)} US symbols. Scanning...")
    # Basic batching to be easier on rate limits
    batch_size = {True: 150, False: 75}[len(base) > 5000]
    while True:
        for i in range(0, len(base), batch_size):
            batch = base[i:i+batch_size]
            hits = scan_once(batch)
            print_hits(hits[:10])
            time.sleep(2.0)

if __name__ == "__main__":
    main()