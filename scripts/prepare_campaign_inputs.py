#!/usr/bin/env python3
"""Prepare per-run telemetry and final sender-summary CSVs from original Influx exports.

This is the preprocessing step that generates the files consumed by
`scripts/analyze_campaign.py`.

Pipeline
--------
original Influx exports in data/source_exports/
    -> select final repeated run-summary record per node
    -> identify each measured run from its final summary and nearest preceding seq=1
    -> export the run telemetry WITHOUT deduplicating node_id+seq
       (deduplication is intentionally performed later by analyze_campaign.py)
    -> export one final run-summary row per node
    -> for 5N-RUN02 and 5N-RUN03, recover the missing beginning of the telemetry
       window from the full-day Influx export using the final summaries from the
       corresponding narrow exports
    -> files in data/prepared/

Important reproducibility choices
---------------------------------
* Sender firmware transmits the final run summary five times.  The last summary
  record for each node is retained.  This is important because a broad export can
  contain a stale/repeated summary from an adjacent acquisition; the last record
  matches the final counters used in the audited analysis.
* Telemetry duplicates are NOT removed here.  analyze_campaign.py applies the
  manuscript rule: deduplicate (node_id, seq), keep the first stored instance.
* The run start for a node is the latest seq=1 record occurring within one hour
  before that node's retained final run summary.  This removes stale/preliminary
  records preceding a restart while preserving the complete measured run.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source_exports"
PREPARED = ROOT / "data" / "prepared"
PREPARED.mkdir(parents=True, exist_ok=True)

# run_id: (narrow/source export, output telemetry filename, output summary filename)
RUNS = {
    "1N-RUN01": (
        "influxdata_2026-08-12T08_19_38Z.csv",
        "BRIDGE_PERIODIC_1N_RUN01_30min_telemetry(1).csv",
        "BRIDGE_PERIODIC_1N_RUN01_run_summary(1).csv",
    ),
    "1N-RUN02": (
        "influxdata_2026-08-12T08_57_23Z.csv",
        "BRIDGE_PERIODIC_1N_RUN02_30min_telemetry(1).csv",
        "BRIDGE_PERIODIC_1N_RUN02_run_summary(1).csv",
    ),
    "1N-RUN03": (
        "influxdata_2026-08-12T09_54_46Z.csv",
        "BRIDGE_PERIODIC_1N_RUN03_30min_telemetry(1).csv",
        "BRIDGE_PERIODIC_1N_RUN03_run_summary(1).csv",
    ),
    "3N-RUN01": (
        "influxdata_2026-08-11T09_49_04Z.csv",
        "BRIDGE_PERIODIC_3N_RUN01_30min_telemetry(1).csv",
        "BRIDGE_PERIODIC_3N_RUN01_run_summary(1).csv",
    ),
    "3N-RUN02": (
        "influxdata_2026-08-11T17_59_32Z.csv",
        "BRIDGE_PERIODIC_3N_RUN02_30min_telemetry(1).csv",
        "BRIDGE_PERIODIC_3N_RUN02_run_summary(1).csv",
    ),
    "3N-RUN03": (
        "influxdata_2026-08-11T16_00_11Z.csv",
        "BRIDGE_PERIODIC_3N_RUN03_30min_telemetry(1).csv",
        "BRIDGE_PERIODIC_3N_RUN03_run_summary(1).csv",
    ),
    "5N-RUN01": (
        "influxdata_2026-08-10T18_53_42Z_1h.csv",
        "BRIDGE_PERIODIC_5N_RUN01_30min_telemetry(2).csv",
        "BRIDGE_PERIODIC_5N_RUN01_run_summary(2).csv",
    ),
    "5N-RUN02": (
        "influxdata_2026-08-10T19_54_50Z.csv",
        "BRIDGE_PERIODIC_5N_RUN02_30min_telemetry(2).csv",
        "BRIDGE_PERIODIC_5N_RUN02_run_summary(2).csv",
    ),
    "5N-RUN03": (
        "influxdata_2026-08-10T20_48_42Z.csv",
        "BRIDGE_PERIODIC_5N_RUN03_30min_telemetry(3).csv",
        "BRIDGE_PERIODIC_5N_RUN03_run_summary(3).csv",
    ),
}

FULL_DAY_RUNS = {"5N-RUN02", "5N-RUN03"}
FULL_DAY_FILE = "influx_full_day_2026-08-10.csv"


def read_flux(path: Path) -> pd.DataFrame:
    """Read an annotated InfluxDB CSV export (Flux #group/#datatype/#default rows)."""
    return pd.read_csv(path, skiprows=3, low_memory=False)


def retain_final_summary_per_node(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the last repeated final run-summary message for every node."""
    if "run_summary" not in df.columns:
        raise ValueError("Input export has no 'run_summary' column")
    summary = df[df["run_summary"].fillna(0).eq(1)].copy()
    if summary.empty:
        raise ValueError("No run-summary rows found")
    summary["_dt"] = pd.to_datetime(summary["time"], utc=True, errors="raise")
    summary = (
        summary.sort_values("_dt")
        .drop_duplicates("node_id", keep="last")
        .drop(columns=["_dt"])
        .sort_values("node_id")
        .reset_index(drop=True)
    )
    return summary


def extract_telemetry_from_export(source_df: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """Extract one measured run per node using its retained final summary as endpoint."""
    work = source_df.copy()
    work["_dt"] = pd.to_datetime(work["time"], utc=True, errors="coerce")
    work["_seq"] = pd.to_numeric(work["seq"], errors="coerce")
    if "run_summary" in work.columns:
        work = work[work["run_summary"].fillna(0).ne(1)].copy()

    parts = []
    for _, row in summary.iterrows():
        node_id = row["node_id"]
        end = pd.to_datetime(row["time"], utc=True)
        final_tx = int(row["node_tx_attempt_total_final"])

        node = work[
            (work["node_id"] == node_id)
            & (work["_dt"] < end)
            & (work["_dt"] > end - pd.Timedelta(hours=1))
        ].copy()

        seq1 = node[node["_seq"].eq(1)]
        if seq1.empty:
            raise RuntimeError(
                f"No seq=1 found for node {node_id} in the hour before final summary {end}"
            )

        # Nearest restart/seq reset preceding the retained final summary.
        start = seq1["_dt"].max()
        node = node[
            (node["_dt"] >= start)
            & node["_seq"].between(1, final_tx, inclusive="both")
        ].copy()
        parts.append(node)

    if not parts:
        raise RuntimeError("No telemetry rows extracted")

    telemetry = (
        pd.concat(parts, ignore_index=True)
        .sort_values(["_dt", "node_id", "_seq"])
        .drop(columns=["_dt", "_seq"], errors="ignore")
        .reset_index(drop=True)
    )
    return telemetry


def main():
    full_day = read_flux(SOURCE / FULL_DAY_FILE)

    report = []
    for run_id, (source_name, telemetry_name, summary_name) in RUNS.items():
        narrow = read_flux(SOURCE / source_name)
        summary = retain_final_summary_per_node(narrow)

        # The narrow 5N RUN02/RUN03 exports miss the beginning of some node streams.
        # Their final sender summaries are reliable, so use them as endpoints while
        # extracting the complete telemetry windows from the full-day export.
        telemetry_source = full_day if run_id in FULL_DAY_RUNS else narrow
        telemetry = extract_telemetry_from_export(telemetry_source, summary)

        telemetry_path = PREPARED / telemetry_name
        summary_path = PREPARED / summary_name
        telemetry.to_csv(telemetry_path, index=False)
        summary.to_csv(summary_path, index=False)

        duplicate_pairs = int(telemetry.duplicated(["node_id", "seq"]).sum())
        report.append(
            {
                "run": run_id,
                "nodes": len(summary),
                "telemetry_rows_pre_dedup": len(telemetry),
                "duplicate_node_seq_rows": duplicate_pairs,
                "sender_tx_total": int(
                    pd.to_numeric(summary["node_tx_attempt_total_final"], errors="raise").sum()
                ),
                "telemetry_file": telemetry_name,
                "summary_file": summary_name,
            }
        )

    report_df = pd.DataFrame(report)
    report_df.to_csv(PREPARED / "preparation_report.csv", index=False)
    print(report_df.to_string(index=False))
    print(f"\nPrepared files written to: {PREPARED}")


if __name__ == "__main__":
    main()
