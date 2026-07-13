#!/usr/bin/env python3
"""
Reproduce Figure 5: timestamping diagnostics.

This script compares the preliminary pre-two-way timestamping runs with
the final two-way gateway-referenced runs used in the main bridge-assisted
campaign.

It generates:
  outputs_expected/timestamping_diagnostics_run_metrics.csv
  outputs_expected/timestamping_diagnostics_summary.csv
  outputs_expected/figures/timestamping_diagnostics.png
  outputs_expected/figures/timestamping_diagnostics.pdf

Assumptions:
- InfluxDB annotated CSV files are read with skiprows=3.
- Duplicates are identified by (node_id, seq), and the first stored instance is retained.
- L_n2g is taken from n2g_latency_ms if present; otherwise it is computed as:
      t_gw_rx_unix_ms - t_node_unix_ms
- L_gateway is taken from g2m_latency_ms if present; otherwise it is computed as:
      t_gw_tx_unix_ms - t_gw_rx_unix_ms
"""

from pathlib import Path
from dataclasses import dataclass
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "outputs_expected"
FIG_DIR = OUT_DIR / "figures"

OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class RunSpec:
    campaign: str
    scenario: int
    scenario_label: str
    run_id: str
    relative_path: str


RUNS = [
    # -------------------------------------------------------------------------
    # Preliminary pre-two-way timestamping runs used for Figure 5.
    # -------------------------------------------------------------------------
    RunSpec(
        "pre_two_way",
        1,
        "1 node",
        "PRE-1N-RUN01",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-05-25T16_46_06Z.csv",
    ),
    RunSpec(
        "pre_two_way",
        1,
        "1 node",
        "PRE-1N-RUN02",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-05-26T14_01_11Z.csv",
    ),

    RunSpec(
        "pre_two_way",
        3,
        "3 nodes",
        "PRE-3N-RUN01",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-06-05T14_26_44Z.csv",
    ),
    RunSpec(
        "pre_two_way",
        3,
        "3 nodes",
        "PRE-3N-RUN02",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-06-07T12_12_05Z.csv",
    ),
    RunSpec(
        "pre_two_way",
        3,
        "3 nodes",
        "PRE-3N-RUN03",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-06-07T12_46_56Z.csv",
    ),

    RunSpec(
        "pre_two_way",
        5,
        "5 nodes",
        "PRE-5N-RUN01",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-06-08T10_05_45Z.csv",
    ),
    RunSpec(
        "pre_two_way",
        5,
        "5 nodes",
        "PRE-5N-RUN02",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-06-09T10_51_33Z.csv",
    ),
    RunSpec(
        "pre_two_way",
        5,
        "5 nodes",
        "PRE-5N-RUN03",
        "timestamping_diagnostics/pre_two_way/influxdata_2026-06-09T12_04_13Z.csv",
    ),

    # -------------------------------------------------------------------------
    # Final two-way bridge-assisted runs from the main campaign.
    # These are the same nine CSV files used for Table 5, Table 6, and Figure 4.
    # -------------------------------------------------------------------------
    RunSpec(
        "final_two_way",
        1,
        "1 node",
        "FINAL-1N-RUN01",
        "final_bridge_two_way/1node/30min_1node_run01/influxdata_2026-06-23T15_24_34Z.csv",
    ),
    RunSpec(
        "final_two_way",
        1,
        "1 node",
        "FINAL-1N-RUN02",
        "final_bridge_two_way/1node/30min_1node_run02/influxdata_2026-06-23T15_56_38Z.csv",
    ),
    RunSpec(
        "final_two_way",
        1,
        "1 node",
        "FINAL-1N-RUN03",
        "final_bridge_two_way/1node/30min_1node_run03/influxdata_2026-06-24T09_36_20Z.csv",
    ),

    RunSpec(
        "final_two_way",
        3,
        "3 nodes",
        "FINAL-3N-RUN01",
        "final_bridge_two_way/3nodes/30min_3nodes_run01/influxdata_2026-06-16T17_24_52Z.csv",
    ),
    RunSpec(
        "final_two_way",
        3,
        "3 nodes",
        "FINAL-3N-RUN02",
        "final_bridge_two_way/3nodes/30min_3nodes_run02/influxdata_2026-06-22T15_21_40Z.csv",
    ),
    RunSpec(
        "final_two_way",
        3,
        "3 nodes",
        "FINAL-3N-RUN03",
        "final_bridge_two_way/3nodes/30min_3nodes_run03/influxdata_2026-06-22T15_54_23Z.csv",
    ),

    RunSpec(
        "final_two_way",
        5,
        "5 nodes",
        "FINAL-5N-RUN01",
        "final_bridge_two_way/5nodes/30min_5nodes_run01/influxdata_2026-06-19T13_02_54Z.csv",
    ),
    RunSpec(
        "final_two_way",
        5,
        "5 nodes",
        "FINAL-5N-RUN02",
        "final_bridge_two_way/5nodes/30min_5nodes_run02/influxdata_2026-06-19T13_51_53Z.csv",
    ),
    RunSpec(
        "final_two_way",
        5,
        "5 nodes",
        "FINAL-5N-RUN03",
        "final_bridge_two_way/5nodes/30min_5nodes_run03/influxdata_2026-06-19T14_28_36Z.csv",
    ),
]


def read_influx_csv(path: Path) -> pd.DataFrame:
    """Read an InfluxDB annotated CSV export."""
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return pd.read_csv(path, skiprows=3)


def to_numeric_if_present(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def prepare_latency_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add standardized latency columns:
      L_n2g_ms
      L_gateway_ms
    """
    df = df.copy()

    to_numeric_if_present(
        df,
        [
            "seq",
            "n2g_latency_ms",
            "g2m_latency_ms",
            "t_gw_rx_unix_ms",
            "t_gw_tx_unix_ms",
            "t_node_unix_ms",
            "node_count",
        ],
    )

    if "time" in df.columns:
        df["time_dt"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    else:
        df["time_dt"] = pd.NaT

    if "node_id" in df.columns and "seq" in df.columns:
        df = df.drop_duplicates(["node_id", "seq"], keep="first").copy()

    if "n2g_latency_ms" in df.columns:
        df["L_n2g_ms"] = df["n2g_latency_ms"]
    else:
        required = ["t_gw_rx_unix_ms", "t_node_unix_ms"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Cannot compute L_n2g_ms; missing columns: {missing}")
        df["L_n2g_ms"] = df["t_gw_rx_unix_ms"] - df["t_node_unix_ms"]

    if "g2m_latency_ms" in df.columns:
        df["L_gateway_ms"] = df["g2m_latency_ms"]
    else:
        required = ["t_gw_tx_unix_ms", "t_gw_rx_unix_ms"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Cannot compute L_gateway_ms; missing columns: {missing}")
        df["L_gateway_ms"] = df["t_gw_tx_unix_ms"] - df["t_gw_rx_unix_ms"]

    return df


def p95(series: pd.Series) -> float:
    return float(series.dropna().quantile(0.95))


def pdr_from_sequence_continuity(df: pd.DataFrame) -> tuple[int, int, float]:
    """
    Compute database-visible PDR from sequence continuity per node_id stream.
    Returns:
      expected_seq, missing_seq, pdr_percent
    """
    if "node_id" not in df.columns or "seq" not in df.columns:
        return 0, 0, np.nan

    expected_seq = 0
    missing_seq = 0

    for _, group in df.groupby("node_id"):
        seq = group["seq"].dropna().astype(int)
        if seq.empty:
            continue

        expected_for_node = int(seq.max() - seq.min() + 1)
        missing_for_node = expected_for_node - int(seq.nunique())

        expected_seq += expected_for_node
        missing_seq += missing_for_node

    pdr_percent = 100.0 * len(df) / expected_seq if expected_seq else np.nan
    return expected_seq, missing_seq, pdr_percent


def run_metrics(spec: RunSpec) -> dict:
    path = DATA_DIR / spec.relative_path
    df_raw = read_influx_csv(path)
    df = prepare_latency_columns(df_raw)

    expected_seq, missing_seq, pdr_percent = pdr_from_sequence_continuity(df)

    node_streams = int(df["node_id"].dropna().nunique()) if "node_id" in df.columns else np.nan

    metadata_values = ""
    if "node_count" in df.columns:
        values = sorted(int(v) for v in df["node_count"].dropna().unique())
        metadata_values = ";".join(str(v) for v in values)

    duration_min = np.nan
    if "time_dt" in df.columns and df["time_dt"].notna().any():
        duration_min = (
            df["time_dt"].max() - df["time_dt"].min()
        ).total_seconds() / 60.0

    return {
        "campaign": spec.campaign,
        "scenario": spec.scenario,
        "scenario_label": spec.scenario_label,
        "run_id": spec.run_id,
        "file": spec.relative_path,
        "records_unique": len(df),
        "node_streams": node_streams,
        "node_count_metadata_values": metadata_values,
        "duration_min": duration_min,
        "expected_seq": expected_seq,
        "missing_seq": missing_seq,
        "pdr_percent": pdr_percent,
        "L_n2g_median_ms": float(df["L_n2g_ms"].dropna().median()),
        "L_n2g_p95_ms": p95(df["L_n2g_ms"]),
        "L_gateway_median_ms": float(df["L_gateway_ms"].dropna().median()),
        "L_gateway_p95_ms": p95(df["L_gateway_ms"]),
    }


def mean_sd(values: pd.Series) -> tuple[float, float]:
    return float(values.mean()), float(values.std(ddof=1))


def build_summary(run_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for campaign in ["pre_two_way", "final_two_way"]:
        for scenario in [1, 3, 5]:
            group = run_df[
                (run_df["campaign"] == campaign)
                & (run_df["scenario"] == scenario)
            ].copy()

            if group.empty:
                continue

            row = {
                "campaign": campaign,
                "scenario": scenario,
                "scenario_label": group["scenario_label"].iloc[0],
                "runs": len(group),
            }

            for col in [
                "pdr_percent",
                "L_n2g_median_ms",
                "L_n2g_p95_ms",
                "L_gateway_median_ms",
                "L_gateway_p95_ms",
            ]:
                mean, sd = mean_sd(group[col])
                row[f"{col}_mean"] = mean
                row[f"{col}_sd"] = sd

            rows.append(row)

    return pd.DataFrame(rows)


def plot_timestamping_diagnostics(summary_df: pd.DataFrame) -> None:
    """
    Reproduce the Figure 5 style:
      - pre-two-way L_n2g median and p95,
      - final two-way L_n2g median and p95,
      - logarithmic y-axis.
    """
    scenarios = [1, 3, 5]
    x_labels = ["1 node", "3 nodes", "5 nodes"]

    def series(campaign: str, metric: str) -> list[float]:
        values = []
        for scenario in scenarios:
            row = summary_df[
                (summary_df["campaign"] == campaign)
                & (summary_df["scenario"] == scenario)
            ]
            if row.empty:
                raise ValueError(f"Missing summary row: {campaign}, {scenario}")
            values.append(float(row[f"{metric}_mean"].iloc[0]))
        return values

    pre_median = series("pre_two_way", "L_n2g_median_ms")
    pre_p95 = series("pre_two_way", "L_n2g_p95_ms")
    final_median = series("final_two_way", "L_n2g_median_ms")
    final_p95 = series("final_two_way", "L_n2g_p95_ms")

    x = np.arange(len(scenarios))

    fig, ax = plt.subplots(figsize=(10.5, 6.2))

    ax.plot(
        x,
        pre_median,
        marker="o",
        linewidth=2,
        label="Pre-two-way, median",
    )
    ax.plot(
        x,
        pre_p95,
        marker="s",
        linewidth=2,
        label="Pre-two-way, p95",
    )
    ax.plot(
        x,
        final_median,
        marker="o",
        linewidth=2,
        linestyle="--",
        label="Final two-way, median",
    )
    ax.plot(
        x,
        final_p95,
        marker="s",
        linewidth=2,
        linestyle="--",
        label="Final two-way, p95",
    )

    ax.set_yscale("log")
    ax.set_ylabel(r"$L_{n2g}$ [ms]")
    ax.set_xlabel("Active sensor nodes")
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.grid(True, which="both", axis="y", alpha=0.35)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.32), ncol=2, frameon=False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "timestamping_diagnostics.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "timestamping_diagnostics.pdf", bbox_inches="tight")
    plt.close(fig)


def write_report(run_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    lines = []
    lines.append("# Timestamping diagnostics verification report")
    lines.append("")
    lines.append("This report is generated automatically by `scripts/reproduce_timestamping_diagnostics.py`.")
    lines.append("")
    lines.append("## Scenario-level values used for Figure 5")
    lines.append("")

    for campaign in ["pre_two_way", "final_two_way"]:
        lines.append(f"### {campaign}")
        lines.append("")
        for scenario in [1, 3, 5]:
            row = summary_df[
                (summary_df["campaign"] == campaign)
                & (summary_df["scenario"] == scenario)
            ].iloc[0]
            lines.append(
                f"- {row['scenario_label']}: "
                f"L_n2g median {row['L_n2g_median_ms_mean']:.1f} ± "
                f"{row['L_n2g_median_ms_sd']:.1f} ms; "
                f"L_n2g p95 {row['L_n2g_p95_ms_mean']:.1f} ± "
                f"{row['L_n2g_p95_ms_sd']:.1f} ms; "
                f"L_gateway median {row['L_gateway_median_ms_mean']:.1f} ± "
                f"{row['L_gateway_median_ms_sd']:.1f} ms; "
                f"L_gateway p95 {row['L_gateway_p95_ms_mean']:.1f} ± "
                f"{row['L_gateway_p95_ms_sd']:.1f} ms."
            )
        lines.append("")

    lines.append("## Run-level files")
    lines.append("")
    for _, row in run_df.iterrows():
        lines.append(
            f"- {row['run_id']}: {row['file']} "
            f"(unique records: {row['records_unique']}, "
            f"node streams: {row['node_streams']}, "
            f"PDR: {row['pdr_percent']:.3f}%)."
        )

    lines.append("")
    lines.append(
        "The figure itself uses the scenario-level mean of run-level medians "
        "and run-level 95th percentiles."
    )

    (OUT_DIR / "timestamping_diagnostics_verification_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    run_df = pd.DataFrame([run_metrics(spec) for spec in RUNS])
    summary_df = build_summary(run_df)

    run_df.to_csv(
        OUT_DIR / "timestamping_diagnostics_run_metrics.csv",
        index=False,
    )
    summary_df.to_csv(
        OUT_DIR / "timestamping_diagnostics_summary.csv",
        index=False,
    )

    plot_timestamping_diagnostics(summary_df)
    write_report(run_df, summary_df)

    print("Generated:")
    print(f"  {OUT_DIR / 'timestamping_diagnostics_run_metrics.csv'}")
    print(f"  {OUT_DIR / 'timestamping_diagnostics_summary.csv'}")
    print(f"  {OUT_DIR / 'timestamping_diagnostics_verification_report.md'}")
    print(f"  {FIG_DIR / 'timestamping_diagnostics.png'}")
    print(f"  {FIG_DIR / 'timestamping_diagnostics.pdf'}")
    print("")
    print("Scenario-level values:")
    for _, row in summary_df.iterrows():
        print(
            f"{row['campaign']}, {row['scenario_label']}: "
            f"L_n2g median {row['L_n2g_median_ms_mean']:.1f} ms, "
            f"L_n2g p95 {row['L_n2g_p95_ms_mean']:.1f} ms, "
            f"L_gateway median {row['L_gateway_median_ms_mean']:.1f} ms, "
            f"L_gateway p95 {row['L_gateway_p95_ms_mean']:.1f} ms"
        )


if __name__ == "__main__":
    main()