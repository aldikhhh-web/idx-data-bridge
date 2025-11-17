# fetch_data.py
# Simple "realtime-ish" fetcher: try yfinance first, else fallback to simple Investing scraper.
# Output: data/tickers.json (committed by GitHub Actions)

import os, json, time
from datetime import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup
import yfinance as yf

REPO_DATA_PATH = "data/tickers.json"
TICKERS_FILE = "tickers.txt"

def fetch_yahoo(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d")  # last 5 days daily
        info = t.info
        if hist.empty:
            return None
        latest = hist.iloc[-1]
        return {
            "source": "yahoo",
            "ticker": ticker,
            "ts": datetime.utcnow().isoformat(),
            "close": float(latest["Close"]),
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "volume": int(latest.get("Volume", 0)),
            "history": hist.reset_index().to_dict(orient="records"),
            "info": {
                "shortName": info.get("shortName"),
                "marketCap": info.get("marketCap")
            }
        }
    except Exception as e:
        # print("yahoo err", ticker, e)
        return None

def fetch_investing(ticker_symbol_without_suffix):
    # Very simple fallback: attempt to search Investing.com summary page
    # NOTE: fragile; may break if site changes.
    try:
        s = requests.Session()
        # quick search
        search_url = f"https://www.investing.com/search/?q={ticker_symbol_without_suffix}"
        r = s.get(search_url, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        # find first link to instruments
        a = soup.select_one("a.js-searchResultItem")
        if not a:
            return None
        href = a.get("href")
        base = "https://www.investing.com"
        page = s.get(base + href, headers={"User-Agent":"Mozilla/5.0"})
        ps = BeautifulSoup(page.text, "html.parser")
        # parse price
        price_el = ps.select_one("span[class*=text-]") or ps.select_one("span#last_last")
        price = None
        if price_el:
            price_txt = price_el.get_text().strip().replace(",","")
            price = float(price_txt)
        # minimal info
        return {
            "source": "investing",
            "ticker": ticker_symbol_without_suffix,
            "ts": datetime.utcnow().isoformat(),
            "close": price,
            "info": {}
        }
    except Exception:
        return None

def load_tickers():
    with open(TICKERS_FILE, "r") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    return lines

def main():
    os.makedirs("data", exist_ok=True)
    tickers = load_tickers()
    out = {"generated_at": datetime.utcnow().isoformat(), "items": []}
    for t in tickers:
        # prefer Yahoo (yfinance) for .JK tickers
        data = None
        if t.endswith(".JK"):
            data = fetch_yahoo(t)
        if not data:
            # try fallback with symbol without .JK
            sym = t.replace(".JK","")
            data = fetch_investing(sym)
        if not data:
            data = {"ticker": t, "ts": datetime.utcnow().isoformat(), "error": "no_data"}
        out["items"].append(data)
        time.sleep(1)  # politeness
    with open(REPO_DATA_PATH, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("Wrote", REPO_DATA_PATH)

if __name__ == "__main__":
    main()
