"""Minimal dashboard for verified, explicitly selected research runs."""

from pathlib import Path

import streamlit as st

from equity_engine.evidence.run import RunEvidence


def main():
    st.set_page_config(page_title="Indian Equity Evidence Engine", layout="wide")
    st.sidebar.title("Research runs")
    root = Path(st.sidebar.text_input("Runs folder", "data/processed/pilot_runs"))
    paths = sorted(root.glob("*/manifest.json"), reverse=True)
    if not paths:
        st.title("System Overview")
        st.info("No run manifests found in the selected folder.")
        st.metric("Data Quality", "UNAVAILABLE")
        return
    selected = st.sidebar.selectbox("Run", paths, format_func=lambda path: path.parent.name)
    render_overview(selected)


def render_overview(manifest_path=None):
    st.title("System Overview")
    if manifest_path is None:
        st.metric("Data Quality", "UNAVAILABLE")
        st.info("Select a run manifest to inspect its recorded quality and evidence.")
        return
    try:
        run = RunEvidence(manifest_path)
    except Exception as error:
        st.metric("Data Quality", "FAILED")
        st.error(f"Run verification failed: {error}")
        return
    manifest = run.manifest
    events, regime = run.frames["events"], run.frames["regime"]
    regime_value = regime.sort("date")["regime"][-1] if regime.height else "UNKNOWN"
    col1, col2, col3 = st.columns(3)
    col1.metric("Market Regime", regime_value)
    col2.metric("Detected Setups", events.height)
    col3.metric("Data Quality", run.quality_status)
    st.write({"Run": manifest["trial_id"], "Research status": manifest["status"],
              "Created": manifest["created_at"], "Input hash": manifest["input_hash"],
              "Price basis cutoff": manifest["price_basis"]["cutoff"]})
    st.warning("Engineering research only. Real-data pilot admission remains incomplete; paper research is not approved.")
    st.subheader("Partitions and cutoffs")
    st.dataframe([{"partition": name, **boundary, **manifest["partition_results"][name]}
                  for name, boundary in manifest["date_boundaries"].items()])
    st.subheader("Sources")
    st.dataframe([{"kind": item["kind"], "path": item["path"], "sha256": item["sha256"],
                   "acquisition": item.get("acquisition", {})} for item in manifest["inputs"]])
    st.subheader("Recorded quality")
    if run.quality is None:
        st.error("Quality results are unavailable. Evidence use and alerts are withheld.")
    else:
        st.dataframe([{"check": check["name"], "status": check["status"],
                       "blocking": check["blocking"], "counts": str(check["counts"]),
                       "detail": check["detail"]} for check in run.quality["checks"]])
        for limitation in run.quality["limitations"]:
            st.caption(limitation)
        if not run.quality["evidence_allowed"]:
            st.error("Blocking data-quality checks failed. Frozen evidence and alerts are withheld.")
    st.subheader("Candidates")
    st.dataframe(events)
    st.subheader("Frozen evidence")
    if run.quality is None or not run.quality["evidence_allowed"]:
        st.info("Frozen evidence is unavailable for consumer use.")
    else:
        st.dataframe([{"snapshot_id": identity, "partition": metadata["partition"],
                       "setup_version": metadata["setup_version"], "cutoff": metadata["data_cutoff"],
                       "observations": frozen.height, "recorded_statistics": str(metadata["statistics"])}
                      for identity, (metadata, frozen) in run.snapshots.items()])
        st.caption("Recorded statistical labels are not a strategy-validity or paper-research admission decision.")
    for warning in manifest["warnings"]:
        st.caption(warning)


if __name__ == "__main__":
    main()
