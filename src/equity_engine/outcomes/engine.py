import polars as pl
from datetime import date
from equity_engine.setups.breakout import SetupEvent, SetupState

class OutcomeEngine:
    def __init__(self, config: dict):
        self.config = config
        self.timeout_days = self.config.get("timeout_days", 20)
        self.watch_expiry_days = self.config.get("watch_expiry_days", 5)
        self.target_r = self.config.get("target_r", None)
        
        costs = self.config.get("transaction_costs", {})
        gst_taxable_rate = sum([
            costs.get("brokerage_pct", 0.0003),
            costs.get("exchange_charges_pct", 0.00003),
            costs.get("sebi_charges_pct", 0.000001),
        ])
        self.cost_rate = sum([
            costs.get("slippage_pct", 0.001),
            costs.get("brokerage_pct", 0.0003),
            costs.get("stt_pct", 0.001),
            costs.get("exchange_charges_pct", 0.00003),
            costs.get("sebi_charges_pct", 0.000001),
            costs.get("stamp_duty_pct", 0.00015),
            gst_taxable_rate * costs.get("gst_pct", 0.0),
        ])
        
    def evaluate_event(self, event: SetupEvent, future_ohlcv: pl.DataFrame) -> dict:
        result = {
            "event_id": event.event_id,
            "instrument_id": event.instrument_id,
            "setup": event.setup_version,
            "detection_date": event.timestamp,
            "final_state": event.state.value,
            "confirmation_date": None,
            "entry_price": None,
            "stop_price": None,
            "exit_date": None,
            "exit_price": None,
            "price_basis": "adjusted" if "adj_close" in future_ohlcv.columns else "raw",
            "raw_entry_price": None,
            "raw_stop_price": None,
            "raw_exit_price": None,
            "gross_realized_r": None,
            "net_realized_r": None,
            "mfe": None,
            "mae": None,
            "hit_1r": False,
            "hit_2r": False
        }
        
        if future_ohlcv.is_empty():
            return result
            
        df = future_ohlcv.sort("date")
        
        # 1. WATCH phase
        watch_rows = df.filter(pl.col("date") >= event.timestamp).head(self.watch_expiry_days)
        if watch_rows.is_empty():
            return result
            
        confirmation_row = None
        for row in watch_rows.iter_rows(named=True):
            close_price = row.get("adj_close") if "adj_close" in row and row["adj_close"] is not None else row["close"]
            if close_price > event.breakout_level:
                confirmation_row = row
                break
                
        if confirmation_row:
            result["confirmation_date"] = confirmation_row["date"]
            result["final_state"] = SetupState.CONFIRMED.value
        else:
            if len(watch_rows) < self.watch_expiry_days:
                # Censored / Dataset ended before expiry window finished
                result["final_state"] = SetupState.WATCH.value
            else:
                result["final_state"] = SetupState.EXPIRED.value
            return result
            
        # 2. ENTRY phase
        post_conf = df.filter(pl.col("date") > result["confirmation_date"])
        if post_conf.is_empty():
            return result
            
        post_conf = post_conf.head(self.timeout_days)
            
        entry_row = post_conf.row(0, named=True)
        entry_price = entry_row.get("adj_open") if "adj_open" in entry_row and entry_row["adj_open"] is not None else entry_row["open"]
        result["entry_price"] = entry_price
        result["raw_entry_price"] = entry_row.get("open")
        
        # Use confirmation ATR if available, else fallback to detection ATR
        atr = confirmation_row.get("atr_14") if confirmation_row and confirmation_row.get("atr_14") is not None else event.features.get("atr_14", 0)
        stop_price = event.breakout_level - 0.5 * atr
        result["stop_price"] = stop_price
        entry_adj_factor = entry_row.get("adj_factor", 1.0)
        result["raw_stop_price"] = stop_price * entry_adj_factor if entry_adj_factor else stop_price
        
        risk = entry_price - stop_price
        if risk <= 0:
            result["final_state"] = SetupState.INVALIDATED.value
            return result
            
        mfe_price = entry_price
        mae_price = entry_price
        
        target_price = entry_price + self.target_r * risk if self.target_r else None
        
        # 3. HOLD phase
        for row in post_conf.iter_rows(named=True):
            high_price = row.get("adj_high") if "adj_high" in row and row["adj_high"] is not None else row["high"]
            low_price = row.get("adj_low") if "adj_low" in row and row["adj_low"] is not None else row["low"]
            open_price = row.get("adj_open") if "adj_open" in row and row["adj_open"] is not None else row["open"]
            
            if high_price > mfe_price:
                mfe_price = high_price
            if low_price < mae_price:
                mae_price = low_price
                
            hit_stop = low_price <= stop_price
            
            target_1r = entry_price + risk
            target_2r = entry_price + 2 * risk
            
            if not hit_stop:
                if high_price >= target_1r:
                    result["hit_1r"] = True
                if high_price >= target_2r:
                    result["hit_2r"] = True
                    
            hit_target_exit = target_price and high_price >= target_price
            
            if hit_stop and hit_target_exit:
                # Conservative convention: assume stop hit first if both in same daily bar
                exit_price = min(open_price, stop_price)
                result["exit_date"] = row["date"]
                result["exit_price"] = exit_price
                result["final_state"] = SetupState.FAILED.value
                break
            elif hit_stop:
                exit_price = min(open_price, stop_price)
                result["exit_date"] = row["date"]
                result["exit_price"] = exit_price
                result["final_state"] = SetupState.FAILED.value
                break
            elif hit_target_exit:
                exit_price = max(open_price, target_price)
                result["exit_date"] = row["date"]
                result["exit_price"] = exit_price
                result["final_state"] = SetupState.COMPLETED.value
                break
                
        if result["exit_date"] is None and len(post_conf) > 0:
            if len(post_conf) == self.timeout_days:
                exit_row = post_conf.row(self.timeout_days - 1, named=True)
                close_price = exit_row.get("adj_close") if "adj_close" in exit_row and exit_row["adj_close"] is not None else exit_row["close"]
                result["exit_date"] = exit_row["date"]
                result["exit_price"] = close_price
                result["final_state"] = SetupState.COMPLETED.value
                
        # 4. CALCULATION phase
        if result["exit_price"] is not None:
            if result["exit_date"] is not None:
                exit_rows = post_conf.filter(pl.col("date") == result["exit_date"])
                if not exit_rows.is_empty():
                    exit_r = exit_rows.row(0, named=True)
                    exit_adj_factor = exit_r.get("adj_factor", 1.0)
                    result["raw_exit_price"] = result["exit_price"] * exit_adj_factor if exit_adj_factor else result["exit_price"]
                else:
                    result["raw_exit_price"] = result["exit_price"]
            else:
                result["raw_exit_price"] = result["exit_price"]
                
            gross_profit = result["exit_price"] - entry_price
            result["gross_realized_r"] = gross_profit / risk
            
            fees = (entry_price * self.cost_rate) + (result["exit_price"] * self.cost_rate)
            net_profit = gross_profit - fees
            result["net_realized_r"] = net_profit / risk
            
        result["mfe"] = (mfe_price - entry_price) / risk
        result["mae"] = (mae_price - entry_price) / risk
        
        return result
