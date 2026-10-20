import yfinance as yf
import pandas as pd
import os
from datetime import datetime

# Pilot Universe: 20 liquid NSE stocks
TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "ASIANPAINT.NS", "AXISBANK.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "BAJFINANCE.NS", "TATASTEEL.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

def generate_pilot_data():
    all_data = []
    corp_actions = []
    
    print("Downloading historical data...")
    for ticker in TICKERS:
        print(f"Fetching {ticker}...")
        stock = yf.Ticker(ticker)
        
        # Download from Jan 1, 2018 to Sept 1, 2024 to get a good multi-year history
        # We need raw prices! yfinance auto-adjusts by default if auto_adjust=True.
        # We must use auto_adjust=False to get raw prices and splits/dividends.
        df = stock.history(start="2018-01-01", end="2024-09-01", auto_adjust=False)
        
        if df.empty:
            continue
            
        symbol = ticker.replace(".NS", "")
        df = df.reset_index()
        
        # We simulate the NEW July 2024 NSE Bhavcopy Format
        # TradDt, BizDt, Sgmt, Src, FinInstrmTp, FinInstrmId, ISIN, TckrSymb, SctySrs, OpnPric, HghPric, LwPric, ClsPric, LastPric, PrvsClsngPric, TtlTradgVol, TtlTrfVal, TtlNbOfTxsExctd
        
        for _, row in df.iterrows():
            # YF dates can have timezone
            dt = row["Date"]
            if hasattr(dt, "tz_localize") and dt.tz is not None:
                dt = dt.tz_localize(None)
                
            dt_str = dt.strftime("%Y-%m-%d")
            
            # Simulated Traded Value (Volume * Close)
            traded_value = row["Volume"] * row["Close"]
            
            all_data.append({
                "TradDt": dt_str,
                "BizDt": dt_str,
                "Sgmt": "CM",
                "Src": "NSE",
                "FinInstrmTp": "EQ",
                "FinInstrmId": "123456",
                "ISIN": f"INE{symbol}01010", # Mock ISIN
                "TckrSymb": symbol,
                "SctySrs": "EQ",
                "OpnPric": round(row["Open"], 2),
                "HghPric": round(row["High"], 2),
                "LwPric": round(row["Low"], 2),
                "ClsPric": round(row["Close"], 2),
                "LastPric": round(row["Close"], 2),
                "PrvsClsngPric": round(row["Close"], 2), # Simplified
                "TtlTradgVol": int(row["Volume"]),
                "TtlTrfVal": round(traded_value, 2),
                "TtlNbOfTxsExctd": 1000 # Mock trades
            })
            
            if row["Stock Splits"] > 0:
                # yfinance reports forward split as ratio (e.g. 2.0 for 2:1)
                corp_actions.append({
                    "TradDt": dt_str,
                    "TckrSymb": symbol,
                    "ActionType": "SPLIT",
                    "Ratio": row["Stock Splits"]
                })
                
    bhav_df = pd.DataFrame(all_data)
    bhav_df.to_csv("data/raw/NSE_Pilot_Bhavcopy.csv", index=False)
    print(f"Saved {len(bhav_df)} records to data/raw/NSE_Pilot_Bhavcopy.csv")
    
    ca_df = pd.DataFrame(corp_actions)
    if not ca_df.empty:
        ca_df.to_csv("data/raw/NSE_Pilot_CorpActions.csv", index=False)
        print(f"Saved {len(ca_df)} corporate actions to data/raw/NSE_Pilot_CorpActions.csv")
        
if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    generate_pilot_data()
