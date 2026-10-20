import polars as pl
import numpy as np

class ControlEngine:
    @staticmethod
    def calculate_metrics(outcomes_df: pl.DataFrame, baseline_r_values: list = None, baseline_type: str = "STATIC", seed: int = 42, **kwargs) -> dict:
        if "net_realized_r" not in outcomes_df.columns:
            return {}
            
        if "setup" in outcomes_df.columns and outcomes_df["setup"].n_unique() > 1:
            raise ValueError("Multiple setup families provided to ControlEngine. Group by setup first.")
        if "partition" in outcomes_df.columns and outcomes_df["partition"].drop_nulls().n_unique() > 1:
            raise ValueError("Multiple research partitions provided. Analyze each partition separately.")
            
        realized_r = outcomes_df["net_realized_r"].drop_nulls().to_numpy()
        
        if len(realized_r) == 0:
            return {}
            
        wins = np.sum(realized_r > 0)
        mean_r = np.mean(realized_r)
        win_rate = wins / len(realized_r)
        
        baseline_mean = np.mean(baseline_r_values) if baseline_r_values else 0.0
        lift = mean_r - baseline_mean
        
        # Cluster-aware bootstrap: For V1 minimum, if we have date clusters, we could resample by date.
        # But we'll do simple bootstrap here, and note dependence in effective_n
        # If dates are provided, we can count unique blocks
        unique_blocks = outcomes_df["detection_date"].n_unique() if "detection_date" in outcomes_df.columns else len(realized_r)
        
        if len(realized_r) > 1:
            rng = np.random.default_rng(seed)
            samples = rng.choice(realized_r, size=(1000, len(realized_r)), replace=True)
            means = np.mean(samples, axis=1)
            lower_ci = np.percentile(means, 2.5)
            upper_ci = np.percentile(means, 97.5)
        else:
            lower_ci, upper_ci = mean_r, mean_r
            
        is_oos = False
        if "is_oos" in outcomes_df.columns:
            is_oos = bool(outcomes_df["is_oos"].fill_null(False).all())
        if "partition" in outcomes_df.columns:
            valid_partition = bool(outcomes_df["partition"].str.to_lowercase().is_in(["validation", "holdout"]).fill_null(False).all())
            is_oos = valid_partition and (is_oos if "is_oos" in outcomes_df.columns else True)
        elif kwargs.get("is_oos", False):
            is_oos = True if "is_oos" not in outcomes_df.columns else is_oos

        if len(realized_r) <= 1 or unique_blocks < 5 or not is_oos:
            if upper_ci < baseline_mean:
                status = "NEGATIVE EDGE"
            else:
                status = "INSUFFICIENT EVIDENCE"
        elif lower_ci > baseline_mean:
            status = "VALIDATED"
        elif upper_ci < baseline_mean:
            status = "NEGATIVE EDGE"
        else:
            status = "NO EDGE FOUND / INSUFFICIENT EVIDENCE"
            
        return {
            "effective_n": len(realized_r),
            "distinct_time_blocks": unique_blocks,
            "mean_r": float(mean_r),
            "ci_lower": float(lower_ci),
            "ci_upper": float(upper_ci),
            "win_rate": float(win_rate),
            "baseline_mean_r": float(baseline_mean),
            "baseline_type": baseline_type,
            "lift": float(lift),
            "status": status,
            "dependence_limitation": "Assumes detection blocks are independent; does not model holding period overlap."
        }
