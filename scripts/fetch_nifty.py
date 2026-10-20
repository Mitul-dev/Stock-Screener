import yfinance as yf
import pandas as pd
import os

def fetch_nifty():
    print("Fetching NIFTY 50...")
    nifty = yf.Ticker("^NSEI")
    df = nifty.history(start="2018-01-01", end="2024-09-01", auto_adjust=False)
    df = df.reset_index()
    
    out = []
    for _, row in df.iterrows():
        dt = row["Date"]
        if hasattr(dt, "tz_localize") and dt.tz is not None:
            dt = dt.tz_localize(None)
        
        out.append({
            "date": dt.strftime("%Y-%m-%d"),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"])
        })
        
    nifty_df = pd.DataFrame(out)
    nifty_df.to_csv("data/raw/NIFTY50.csv", index=False)
    print(f"Saved {len(nifty_df)} records to data/raw/NIFTY50.csv")

if __name__ == "__main__":
    fetch_nifty()
