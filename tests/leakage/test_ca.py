import polars as pl

def test_ca():
    df = pl.DataFrame({
        "date": [1, 2, 3],
        "open": [100.0, 50.0, 52.0],
        "high": [100.0, 50.0, 52.0],
        "low": [100.0, 50.0, 52.0],
        "close": [100.0, 50.0, 52.0],
        "volume": [100.0, 200.0, 200.0]
    })
    
    actions = pl.DataFrame({
        "date": [2],
        "factor": [2.0]
    })
    
    from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
    adj = CorporateActionAdjustor.adjust_ohlcv(df, actions)
    adj_dict = adj.to_dicts()
    print("Row 0:", adj_dict[0])
    print("Row 1:", adj_dict[1])
    print("Row 2:", adj_dict[2])

if __name__ == "__main__":
    test_ca()
