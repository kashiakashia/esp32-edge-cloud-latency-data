#!/usr/bin/env python3
"""
Reproduce the main bridge-assisted two-way campaign results.

This script reads the nine InfluxDB CSV exports from:
  data/final_bridge_two_way/

It reproduces:
  - scenario-level data-quality metrics used in Table 5,
  - scenario-level latency metrics used in Table 6 and the abstract,
  - run-level appendix tables,
  - Figure 4: bridge_scaling_summary.png and bridge_scaling_summary.pdf.

The analysis intentionally treats PDR as database-visible packet continuity.
Duplicates are identified by node_id + seq, and the first stored instance is retained.
"""

from pathlib import Path
from dataclasses import dataclass
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "final_bridge_two_way"
OUT_DIR = ROOT / "outputs_expected"
FIG_DIR = OUT_DIR / "figures"

OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class RunSpec:
    scenario: int
    scenario_label: str
    run_id: str
    relative_path: str


RUNS = [
    RunSpec(1, "1 node",  "1N-RUN01", "1node/30min_1node_run01/influxdata_2026-06-23T15_24_34Z.csv"),
    RunSpec(1, "1 node",  "1N-RUN02", "1node/30min_1node_run02/influxdata_2026-06-23T15_56_38Z.csv"),
    RunSpec(1, "1 node",  "1N-RUN03", "1node/30min_1node_run03/influxdata_2026-06-24T09_36_20Z.csv"),

    RunSpec(3, "3 nodes", "3N-RUN01", "3nodes/30min_3nodes_run01/influxdata_2026-06-16T17_24_52Z.csv"),
    RunSpec(3, "3 nodes", "3N-RUN02", "3nodes/30min_3nodes_run02/influxdata_2026-06-22T15_21_40Z.csv"),
    RunSpec(3, "3 nodes", "3N-RUN03", "3nodes/30min_3nodes_run03/influxdata_2026-06-22T15_54_23Z.csv"),

    RunSpec(5, "5 nodes", "5N-RUN01", "5nodes/30min_5nodes_run01/influxdata_2026-06-19T13_02_54Z.csv"),
    RunSpec(5, "5 nodes", "5N-RUN02", "5nodes/30min_5nodes_run02/influxdata_2026-06-19T13_51_53Z.csv"),
    RunSpec(5, "5 nodes", "5N-RUN03", "5nodes/30min_5nodes_run03/influxdata_2026-06-19T14_28_36Z.csv"),
]


def read_influx_csv(path: Path) -> pd.DataFrame:
    """Read an InfluxDB annotated CSV export."""
    return pd.read_csv(path, skiprows=3)


def percentile_95(series: pd.Series) -> float:
    return float(series.dropna().quantile(0.95))


def run_metrics(spec: RunSpec) -> dict:
    path = DATA_DIR / spec.relative_path
    df = read_influx_csv(path).copy()

    required = [
        "time",
        "node_id",
        "seq",
        "n2g_latency_ms",
        "g2m_latency_ms",
        "t_gw_tx_unix_ms",
        "t_node_unix_ms",
    ]
    missing_columns = [c for c in required if c not in df.columns]
    if missing_columns:
        raise ValueError(f"{path.name}: missing required columns: {missing_columns}")

    for col in [
        "seq",
        "n2g_latency_ms",
        "g2m_latency_ms",
        "t_gw_tx_unix_ms",
        "t_node_unix_ms",
        "sync_delay_ms",
        "sync_rtt_ms",
        "node_count",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["time_dt"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    if df["time_dt"].isna().all():
        raise ValueError(f"{path.name}: all backend timestamps failed to parse")

    # Backend timestamp is represented by the InfluxDB record time.
    df["t_cloud_ms"] = df["time_dt"].astype("int64") / 1e6

    # Latency components.
    df["l_backend_ms"] = df["t_cloud_ms"] - df["t_gw_tx_unix_ms"]
    df["l_total_ms"] = df["t_cloud_ms"] - df["t_node_unix_ms"]

    raw_records = len(df)
    unique = df.drop_duplicates(["node_id", "seq"], keep="first").copy()
    duplicate_records = raw_records - len(unique)

    expected_seq = 0
    missing_seq = 0
    max_gap_s = 0.0

    for node_id, group in unique.groupby("node_id"):
        seq = group["seq"].dropna().astype(int)
        if seq.empty:
            continue

        expected_for_node = int(seq.max() - seq.min() + 1)
        missing_for_node = expected_for_node - int(seq.nunique())
        expected_seq += expected_for_node
        missing_seq += missing_for_node

        ordered = group.sort_values("time_dt")
        gaps = ordered["time_dt"].diff().dt.total_seconds()
        if gaps.notna().any():
            max_gap_s = max(max_gap_s, float(gaps.max()))

    pdr_percent = 100.0 * len(unique) / expected_seq if expected_seq else np.nan
    duration_min = (
        unique["time_dt"].max() - unique["time_dt"].min()
    ).total_seconds() / 60.0

    def med_p95(col: str) -> tuple[float, float]:
        values = unique[col].dropna()
        return float(values.median()), percentile_95(values)

    n2g_median, n2g_p95 = med_p95("n2g_latency_ms")
    gateway_median, gateway_p95 = med_p95("g2m_latency_ms")
    backend_median, backend_p95 = med_p95("l_backend_ms")
    total_median, total_p95 = med_p95("l_total_ms")

    sync_delay_median = np.nan
    sync_delay_p95 = np.nan
    if "sync_delay_ms" in unique.columns:
        sync_delay_median, sync_delay_p95 = med_p95("sync_delay_ms")

    stored_node_count_values = []
    if "node_count" in df.columns:
        stored_node_count_values = sorted(
            int(v) for v in df["node_count"].dropna().unique()
        )
    actual_node_streams = int(unique["node_id"].dropna().nunique())

    return {
        "scenario": spec.scenario,
        "scenario_label": spec.scenario_label,
        "run_id": spec.run_id,
        "file": spec.relative_path,
        "duration_min": duration_min,
        "raw_records": raw_records,
        "unique_packets": len(unique),
        "expected_seq": expected_seq,
        "missing_seq": missing_seq,
        "duplicates": duplicate_records,
        "pdr_percent": pdr_percent,
        "max_gap_s": max_gap_s,
        "actual_node_streams": actual_node_streams,
        "node_count_metadata_values": ";".join(map(str, stored_node_count_values)),
        "n2g_median_ms": n2g_median,
        "n2g_p95_ms": n2g_p95,
        "gateway_median_ms": gateway_median,
        "gateway_p95_ms": gateway_p95,
        "backend_median_ms": backend_median,
        "backend_p95_ms": backend_p95,
        "total_median_ms": total_median,
        "total_p95_ms": total_p95,
        "sync_delay_median_ms": sync_delay_median,
        "sync_delay_p95_ms": sync_delay_p95,
    }


def mean_sd(series: pd.Series) -> tuple[float, float]:
    return float(series.mean()), float(series.std(ddof=1))


def fmt_mean_sd(mean: float, sd: float, decimals: int = 1) -> str:
    return f"{mean:.{decimals}f} ± {sd:.{decimals}f}"


def build_scenario_tables(run_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    quality_rows = []
    latency_rows = []

    for scenario in [1, 3, 5]:
        group = run_df.loc[run_df["scenario"] == scenario].copy()
        label = group["scenario_label"].iloc[0]

        quality = {"Scenario": label, "Runs": len(group)}
        for col, label_col, decimals in [
            ("unique_packets", "Unique packets", 1),
            ("missing_seq", "Missing seq.", 1),
            ("duplicates", "Duplicates", 1),
            ("pdr_percent", "Stored PDR [%]", 2),
            ("max_gap_s", "Max gap [s]", 2),
        ]:
            mean, sd = mean_sd(group[col])
            quality[label_col] = fmt_mean_sd(mean, sd, decimals)
        quality_rows.append(quality)

        latency = {"Scenario": label, "Runs": len(group)}
        for med_col, p95_col, prefix in [
            ("n2g_median_ms", "n2g_p95_ms", "L_n2g"),
            ("gateway_median_ms", "gateway_p95_ms", "L_gateway"),
            ("backend_median_ms", "backend_p95_ms", "L_backend"),
            ("total_median_ms", "total_p95_ms", "L_total"),
            ("sync_delay_median_ms", "sync_delay_p95_ms", "d_sync"),
        ]:
            med_mean, med_sd = mean_sd(group[med_col])
            p95_mean, p95_sd = mean_sd(group[p95_col])
            latency[f"{prefix} median [ms]"] = fmt_mean_sd(med_mean, med_sd, 1)
            latency[f"{prefix} p95 [ms]"] = fmt_mean_sd(p95_mean, p95_sd, 1)
        latency_rows.append(latency)

    return pd.DataFrame(quality_rows), pd.DataFrame(latency_rows)


def build_numeric_scenario_summary(run_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario in [1, 3, 5]:
        group = run_df.loc[run_df["scenario"] == scenario].copy()
        row = {
            "scenario": scenario,
            "scenario_label": group["scenario_label"].iloc[0],
            "runs": len(group),
        }
        for col in [
            "unique_packets",
            "missing_seq",
            "duplicates",
            "pdr_percent",
            "max_gap_s",
            "n2g_median_ms",
            "n2g_p95_ms",
            "gateway_median_ms",
            "gateway_p95_ms",
            "backend_median_ms",
            "backend_p95_ms",
            "total_median_ms",
            "total_p95_ms",
            "sync_delay_median_ms",
            "sync_delay_p95_ms",
        ]:
            mean, sd = mean_sd(group[col])
            row[f"{col}_mean"] = mean
            row[f"{col}_sd"] = sd
        rows.append(row)
    return pd.DataFrame(rows)


def plot_figure4(run_df: pd.DataFrame) -> None:
    scenarios = [1, 3, 5]
    x = np.arange(len(scenarios))

    def arr(col: str, op: str = "mean") -> np.ndarray:
        values = []
        for scenario in scenarios:
            group = run_df.loc[run_df["scenario"] == scenario, col]
            values.append(float(group.mean()) if op == "mean" else float(group.std(ddof=1)))
        return np.array(values)

    pdr_runs = {
        s: run_df.loc[run_df["scenario"] == s, "pdr_percent"].to_numpy()
        for s in scenarios
    }
    pdr_mean = np.array([pdr_runs[s].mean() for s in scenarios])

    n2g_p95_mean = arr("n2g_p95_ms", "mean")
    n2g_p95_sd = arr("n2g_p95_ms", "sd")
    gateway_p95_mean = arr("gateway_p95_ms", "mean")
    gateway_p95_sd = arr("gateway_p95_ms", "sd")

    n2g_med_mean = arr("n2g_median_ms", "mean")
    gateway_med_mean = arr("gateway_median_ms", "mean")
    backend_med_mean = arr("backend_median_ms", "mean")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel (a): individual run PDR and scenario mean
    ax = axes[0]
    jitter = np.array([-0.055, 0.0, 0.055])
    for i, scenario in enumerate(scenarios):
        vals = pdr_runs[scenario]
        ax.scatter(
            np.full(len(vals), x[i]) + jitter[:len(vals)],
            vals,
            s=36,
            marker="o",
            color="tab:blue",
            zorder=3,
        )
        ax.scatter(
            x[i],
            pdr_mean[i],
            s=90,
            marker="D",
            color="black",
            zorder=4,
        )

    legend_handles = [
        Line2D([0], [0], marker="o", linestyle="None", markersize=7,
               markerfacecolor="tab:blue", markeredgecolor="tab:blue",
               label="Individual runs"),
        Line2D([0], [0], marker="D", linestyle="None", markersize=8,
               markerfacecolor="black", markeredgecolor="black",
               label="Mean"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", frameon=True)
    ax.set_title("(a) Packet delivery")
    ax.set_xlabel("Active sensor nodes")
    ax.set_ylabel("PDR [%]")
    ax.set_xticks(x, scenarios)
    ax.set_ylim(98.8, 100.02)
    ax.set_yticks(np.arange(98.8, 100.01, 0.2))
    ax.grid(axis="y", alpha=0.35)

    # Panel (b): local timing p95
    ax = axes[1]
    width = 0.36
    ax.bar(
        x - width / 2,
        n2g_p95_mean,
        width,
        yerr=n2g_p95_sd,
        capsize=4,
        label=r"$L_{n2g}$ p95",
        color="tab:blue",
    )
    ax.bar(
        x + width / 2,
        gateway_p95_mean,
        width,
        yerr=gateway_p95_sd,
        capsize=4,
        label=r"$L_{gateway}$ p95",
        color="tab:orange",
    )
    ax.set_title("(b) Local timing")
    ax.set_xlabel("Active sensor nodes")
    ax.set_ylabel("Latency [ms]")
    ax.set_xticks(x, scenarios)
    ax.set_ylim(0, 110)
    ax.set_yticks(np.arange(0, 111, 10))
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.35)
    ax.set_axisbelow(True)

    # Panel (c): median component decomposition
    ax = axes[2]
    ax.bar(x, n2g_med_mean, label=r"$L_{n2g}$", color="tab:blue")
    ax.bar(
        x,
        gateway_med_mean,
        bottom=n2g_med_mean,
        label=r"$L_{gateway}$",
        color="tab:orange",
    )
    ax.bar(
        x,
        backend_med_mean,
        bottom=n2g_med_mean + gateway_med_mean,
        label=r"$L_{backend}$",
        color="tab:green",
    )
    ax.set_title("(c) Latency decomposition")
    ax.set_xlabel("Active sensor nodes")
    ax.set_ylabel("Median latency [ms]")
    ax.set_xticks(x, scenarios)
    ax.set_ylim(0, 1150)
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.35)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "bridge_scaling_summary.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "bridge_scaling_summary.pdf", bbox_inches="tight")
    plt.close(fig)


def write_verification_report(run_df: pd.DataFrame, scenario_numeric: pd.DataFrame) -> None:
    report = []
    report.append("# Verification report")
    report.append("")
    report.append("This report is generated automatically by `scripts/reproduce_main_results_and_figure4.py`.")
    report.append("")
    report.append("## Run-level PDR values used in Figure 4(a)")
    report.append("")
    for scenario in [1, 3, 5]:
        group = run_df.loc[run_df["scenario"] == scenario]
        label = group["scenario_label"].iloc[0]
        vals = ", ".join(f"{v:.3f}%" for v in group["pdr_percent"])
        report.append(f"- {label}: {vals}")
    report.append("")
    report.append("## Scenario-level values used in the abstract")
    report.append("")
    for _, row in scenario_numeric.iterrows():
        report.append(
            f"- {row['scenario_label']}: "
            f"PDR {row['pdr_percent_mean']:.2f} ± {row['pdr_percent_sd']:.2f}%; "
            f"L_n2g median/p95 {row['n2g_median_ms_mean']:.1f}/"
            f"{row['n2g_p95_ms_mean']:.1f} ms; "
            f"L_gateway median/p95 {row['gateway_median_ms_mean']:.1f}/"
            f"{row['gateway_p95_ms_mean']:.1f} ms."
        )
    report.append("")
    report.append("## Metadata notes")
    report.append("")
    notes = []
    for _, row in run_df.iterrows():
        metadata_values = str(row["node_count_metadata_values"])
        actual = int(row["actual_node_streams"])
        if metadata_values and metadata_values != str(actual):
            notes.append(
                f"- {row['run_id']} ({row['file']}): node_count metadata = "
                f"{metadata_values}, actual distinct node_id streams = {actual}."
            )
    if notes:
        report.extend(notes)
    else:
        report.append("- No mismatch between stored node_count metadata and actual distinct node_id streams was detected.")
    report.append("")
    report.append("The scenario labels in this package are defined by the run manifest, not solely by the stored `node_count` field.")
    (OUT_DIR / "verification_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    run_df = pd.DataFrame([run_metrics(spec) for spec in RUNS])

    run_df.to_csv(OUT_DIR / "appendix_run_metrics_numeric.csv", index=False)

    quality_table, latency_table = build_scenario_tables(run_df)
    quality_table.to_csv(OUT_DIR / "table5_scenario_quality.csv", index=False)
    latency_table.to_csv(OUT_DIR / "table6_scenario_latency.csv", index=False)

    scenario_numeric = build_numeric_scenario_summary(run_df)
    scenario_numeric.to_csv(OUT_DIR / "scenario_summary_numeric.csv", index=False)

    # More focused appendix exports for convenience.
    run_quality_cols = [
        "scenario_label", "run_id", "file", "duration_min", "unique_packets",
        "missing_seq", "duplicates", "pdr_percent", "max_gap_s",
        "actual_node_streams", "node_count_metadata_values"
    ]
    run_latency_cols = [
        "scenario_label", "run_id", "n2g_median_ms", "n2g_p95_ms",
        "gateway_median_ms", "gateway_p95_ms", "backend_median_ms",
        "backend_p95_ms", "total_median_ms", "total_p95_ms",
        "sync_delay_median_ms", "sync_delay_p95_ms"
    ]
    run_df[run_quality_cols].to_csv(OUT_DIR / "appendix_run_quality.csv", index=False)
    run_df[run_latency_cols].to_csv(OUT_DIR / "appendix_run_latency.csv", index=False)

    plot_figure4(run_df)
    write_verification_report(run_df, scenario_numeric)

    print("Generated outputs in:", OUT_DIR)
    print("Generated Figure 4 in:", FIG_DIR)
    print("")
    print("Scenario-level abstract values:")
    for _, row in scenario_numeric.iterrows():
        print(
            f"{row['scenario_label']}: "
            f"PDR {row['pdr_percent_mean']:.2f} ± {row['pdr_percent_sd']:.2f}%, "
            f"L_n2g median/p95 {row['n2g_median_ms_mean']:.1f}/{row['n2g_p95_ms_mean']:.1f} ms, "
            f"L_gateway median/p95 {row['gateway_median_ms_mean']:.1f}/{row['gateway_p95_ms_mean']:.1f} ms"
        )


if __name__ == "__main__":
    main()
