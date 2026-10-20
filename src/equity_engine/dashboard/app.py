import streamlit as st
from pathlib import Path
import polars as pl

def main():
    st.set_page_config(page_title="Indian Equity Evidence Engine", layout="wide")
    
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["Overview", "Scanner", "Setup Detail", "Research", "Forward Test"]
    )
    
    if page == "Overview":
        render_overview()
    elif page == "Scanner":
        render_scanner()
    elif page == "Setup Detail":
        render_setup_detail()
    elif page == "Research":
        render_research()
    elif page == "Forward Test":
        render_forward_test()

def render_overview():
    st.title("System Overview")
    
    regime = "UNKNOWN"
    detected_count = "0"
    data_quality = "UNKNOWN"
    
    outcomes_path = Path("data/processed/pilot_outcomes.parquet")
    if outcomes_path.exists():
        try:
            outcomes = pl.read_parquet(outcomes_path)
            detected_count = str(len(outcomes))
            data_quality = "VALIDATED" if len(outcomes) > 0 else "UNKNOWN"
        except Exception:
            pass
            
    nifty_path = Path("data/raw/NIFTY50.csv")
    if nifty_path.exists():
        try:
            nifty = pl.read_csv(nifty_path)
            if "close" in nifty.columns and len(nifty) >= 200:
                sma_200 = float(nifty["close"].tail(200).mean())
                latest_close = float(nifty["close"][-1])
                regime = "UPTREND" if latest_close >= sma_200 else "NEUTRAL"
        except Exception:
            pass

    col1, col2, col3 = st.columns(3)
    col1.metric("Market Regime", regime)
    col2.metric("Detected Setups", detected_count)
    col3.metric("Data Quality", data_quality)
    
    st.subheader("Recent Alerts")
    st.info("No recent alerts in the outbox.")

def render_scanner():
    st.title("Scanner")
    st.write("Filter eligible setups by regime, liquidity, and state.")
    
def render_setup_detail():
    st.title("Setup Detail")
    st.write("Detailed chart and evidence for a specific setup.")
    
def render_research():
    st.title("Research & Evidence")
    st.write("Historical evidence snapshots and holdout statistics.")

def render_forward_test():
    st.title("Forward Test")
    st.write("Live tracker of all out-of-sample detected events.")

if __name__ == "__main__":
    main()
