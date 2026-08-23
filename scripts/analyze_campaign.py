#!/usr/bin/env python3
"""Reproduce the bridge-assisted campaign tables and figures from raw exports.

Rules mirrored from the manuscript:
- one 30 min run is one independent replicate;
- telemetry is deduplicated by (node_id, seq), keeping the first stored instance;
- no latency outlier is removed solely because it is large;
- exact database-visible PDR uses final sender TX attempts from run summaries;
- 5N RUN02/RUN03 beginnings are recovered from the full-day Influx export using
  the nearest seq=1 preceding each node's final run summary.

This patched version keeps the final corrected numbers from the audited analysis
but restores the more readable manuscript-oriented figure style requested by the author:
- ECDF legend includes packet counts n;
- run-level mean plot uses 1N / 3N / 5N labels and the older visual style;
- throughput plot returns to the 4-stage style (TX, Gateway RX, Gateway published, Stored),
  while gateway RX and published remain reconciled telemetry-stage rates as described
  in the manuscript.
"""
from pathlib import Path
import math
import shutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PREPARED = ROOT / "data" / "prepared"
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
FIGURES_MANUSCRIPT = ROOT / "outputs" / "figures_for_manuscript"
DOC_IMAGES = ROOT / "docs" / "images"
for p in (PROCESSED, TABLES, FIGURES, FIGURES_MANUSCRIPT):
    p.mkdir(parents=True, exist_ok=True)

RUNS = {
    "1N-RUN01": ("BRIDGE_PERIODIC_1N_RUN01_30min_telemetry(1).csv", "BRIDGE_PERIODIC_1N_RUN01_run_summary(1).csv"),
    "1N-RUN02": ("BRIDGE_PERIODIC_1N_RUN02_30min_telemetry(1).csv", "BRIDGE_PERIODIC_1N_RUN02_run_summary(1).csv"),
    "1N-RUN03": ("BRIDGE_PERIODIC_1N_RUN03_30min_telemetry(1).csv", "BRIDGE_PERIODIC_1N_RUN03_run_summary(1).csv"),
    "3N-RUN01": ("BRIDGE_PERIODIC_3N_RUN01_30min_telemetry(1).csv", "BRIDGE_PERIODIC_3N_RUN01_run_summary(1).csv"),
    "3N-RUN02": ("BRIDGE_PERIODIC_3N_RUN02_30min_telemetry(1).csv", "BRIDGE_PERIODIC_3N_RUN02_run_summary(1).csv"),
    "3N-RUN03": ("BRIDGE_PERIODIC_3N_RUN03_30min_telemetry(1).csv", "BRIDGE_PERIODIC_3N_RUN03_run_summary(1).csv"),
    "5N-RUN01": ("BRIDGE_PERIODIC_5N_RUN01_30min_telemetry(2).csv", "BRIDGE_PERIODIC_5N_RUN01_run_summary(2).csv"),
    "5N-RUN02": ("BRIDGE_PERIODIC_5N_RUN02_30min_telemetry(2).csv", "BRIDGE_PERIODIC_5N_RUN02_run_summary(2).csv"),
    "5N-RUN03": ("BRIDGE_PERIODIC_5N_RUN03_30min_telemetry(3).csv", "BRIDGE_PERIODIC_5N_RUN03_run_summary(3).csv"),
}

SCENARIO_COLORS = {1: 'C0', 3: 'C1', 5: 'C2'}


def q95(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return np.nan
    return float(s.quantile(0.95, interpolation="lower"))


def dedup_telemetry(df):
    out = df.copy()
    out = out[out.get("run_summary", 0).fillna(0).ne(1)] if "run_summary" in out else out
    out["seq"] = pd.to_numeric(out["seq"], errors="coerce")
    out = out[out["node_id"].notna() & out["seq"].notna()].copy()
    if "time" in out.columns:
        out["_dt"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
        out = out.sort_values("_dt")
    out = out.drop_duplicates(["node_id", "seq"], keep="first")
    return out.drop(columns=["_dt"], errors="ignore")


def summarize_run(run_id, df, summary):
    tx = int(pd.to_numeric(summary["node_tx_attempt_total_final"], errors="coerce").sum())
    ack = int(pd.to_numeric(summary["node_tx_ack_true_total_final"], errors="coerce").sum())
    ack_false = int(pd.to_numeric(summary["node_tx_ack_false_total_final"], errors="coerce").sum())
    send_err = int(pd.to_numeric(summary["node_tx_send_error_total_final"], errors="coerce").sum())
    duration_s = float(pd.to_numeric(summary["node_run_elapsed_ms_final"], errors="coerce").max()) / 1000.0
    n = len(df)

    def mean(col):
        return float(pd.to_numeric(df[col], errors="coerce").mean()) if col in df else np.nan

    def med(col):
        return float(pd.to_numeric(df[col], errors="coerce").median()) if col in df else np.nan

    result = {
        "run": run_id,
        "nodes": int(run_id[0]),
        "stored_unique": n,
        "sender_tx": tx,
        "sender_ack_true": ack,
        "sender_ack_false": ack_false,
        "sender_send_errors": send_err,
        "stored_pdr_pct": 100 * n / tx,
        "duration_s": duration_s,
        "tx_rate_pkt_s": tx / duration_s,
        "gateway_rx_rate_pkt_s": tx / duration_s,  # reconciled telemetry-only stage rate
        "gateway_published_rate_pkt_s": tx / duration_s,  # reconciled telemetry-only stage rate
        "stored_rate_pkt_s": n / duration_s,
        "n2g_mean_ms": mean("n2g_latency_ms"),
        "n2g_median_ms": med("n2g_latency_ms"),
        "n2g_p95_ms": q95(df["n2g_latency_ms"]),
        "gateway_mean_ms": mean("g2m_latency_ms"),
        "gateway_median_ms": med("g2m_latency_ms"),
        "gateway_p95_ms": q95(df["g2m_latency_ms"]),
        "backend_mean_ms": mean("backend_latency_ms") if "backend_latency_ms" in df else np.nan,
        "total_mean_ms": mean("total_latency_ms") if "total_latency_ms" in df else np.nan,
        "sync_w_median_ms": med("sync_offset_span_ms"),
        "sync_w_p95_ms": q95(df["sync_offset_span_ms"]) if "sync_offset_span_ms" in df else np.nan,
        "sync_valid_probes_median": med("sync_valid_probes"),
        "sensor_read_mean_ms": mean("sensor_read_ms"),
        "build_to_send_mean_ms": mean("node_build_to_send_ms"),
    }

    if math.isnan(result["backend_mean_ms"]) and {"t_gw_tx_unix_ms", "time"}.issubset(df.columns):
        cloud = pd.to_datetime(df["time"], utc=True, errors="coerce").astype("int64") / 1e6
        txms = pd.to_numeric(df["t_gw_tx_unix_ms"], errors="coerce")
        result["backend_mean_ms"] = float((cloud - txms).mean())
    if math.isnan(result["total_mean_ms"]) and {"t_node_unix_ms", "time"}.issubset(df.columns):
        cloud = pd.to_datetime(df["time"], utc=True, errors="coerce").astype("int64") / 1e6
        tn = pd.to_numeric(df["t_node_unix_ms"], errors="coerce")
        result["total_mean_ms"] = float((cloud - tn).mean())
    return result


def save_figure_to_all(fig, filename):
    for target_dir in (FIGURES, FIGURES_MANUSCRIPT):
        fig.savefig(target_dir / filename, dpi=300, bbox_inches='tight')
    if DOC_IMAGES.exists():
        fig.savefig(DOC_IMAGES / filename, dpi=300, bbox_inches='tight')


def main():
    run_rows = []
    all_processed = []
    per_node = []

    for run_id, (tele_name, sum_name) in RUNS.items():
        summary = pd.read_csv(PREPARED / sum_name)
        tele = pd.read_csv(PREPARED / tele_name, low_memory=False)
        tele = dedup_telemetry(tele)
        tele["analysis_run_id"] = run_id
        tele["analysis_node_count"] = int(run_id[0])
        out_path = PROCESSED / f"{run_id}_telemetry_clean.csv"
        tele.to_csv(out_path, index=False)
        all_processed.append(tele)
        run_rows.append(summarize_run(run_id, tele, summary))
        for nid, g in tele.groupby("node_id"):
            final = summary.loc[summary.node_id.eq(nid), "node_tx_attempt_total_final"]
            tx = int(final.iloc[0]) if len(final) else np.nan
            per_node.append({
                "run": run_id,
                "nodes": int(run_id[0]),
                "node_id": nid,
                "stored_unique": len(g),
                "sender_tx": tx,
                "stored_pdr_pct": 100 * len(g) / tx if tx else np.nan,
                "n2g_mean_ms": pd.to_numeric(g.n2g_latency_ms, errors='coerce').mean(),
                "n2g_median_ms": pd.to_numeric(g.n2g_latency_ms, errors='coerce').median(),
                "n2g_p95_ms": q95(g.n2g_latency_ms),
                "sync_w_median_ms": pd.to_numeric(g.sync_offset_span_ms, errors='coerce').median(),
            })

    runs = pd.DataFrame(run_rows).sort_values(["nodes", "run"])
    runs.to_csv(TABLES / "run_level_metrics.csv", index=False)
    pd.DataFrame(per_node).to_csv(TABLES / "per_node_metrics.csv", index=False)

    scen = []
    for n, g in runs.groupby("nodes"):
        row = {"nodes": n}
        for col in [
            "n2g_mean_ms", "gateway_mean_ms", "backend_mean_ms", "total_mean_ms",
            "tx_rate_pkt_s", "gateway_rx_rate_pkt_s", "gateway_published_rate_pkt_s",
            "stored_rate_pkt_s", "stored_pdr_pct"
        ]:
            row[col + "_runmean"] = g[col].mean()
            row[col + "_runSD"] = g[col].std(ddof=1)
        row["n2g_p95_run_values"] = ";".join(f"{x:.0f}" for x in g.n2g_p95_ms)
        row["sync_w_median_run_values"] = ";".join(f"{x:.0f}" for x in g.sync_w_median_ms)
        row["sync_w_p95_run_values"] = ";".join(f"{x:.0f}" for x in g.sync_w_p95_ms)
        scen.append(row)
    scenarios = pd.DataFrame(scen)
    scenarios.to_csv(TABLES / "scenario_summary.csv", index=False)

    reliability = runs[[
        "run", "nodes", "sender_tx", "sender_ack_true", "sender_ack_false",
        "sender_send_errors", "stored_unique", "stored_pdr_pct"
    ]].copy()
    reliability["missing_database_records"] = reliability.sender_tx - reliability.stored_unique
    reliability.to_csv(TABLES / "reliability_exact_pdr.csv", index=False)

    runs[[
        "run", "nodes", "tx_rate_pkt_s", "gateway_rx_rate_pkt_s",
        "gateway_published_rate_pkt_s", "stored_rate_pkt_s"
    ]].to_csv(TABLES / "throughput.csv", index=False)
    runs[["run", "nodes", "sync_w_median_ms", "sync_w_p95_ms", "sync_valid_probes_median"]].to_csv(TABLES / "sync_quality.csv", index=False)

    combined = pd.concat(all_processed, ignore_index=True)

    # Figure 1: ECDF in the old manuscript-oriented style with n in legend.
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    for n in [1, 3, 5]:
        g = combined[combined["analysis_node_count"].eq(n)]
        x = np.sort(pd.to_numeric(g.n2g_latency_ms, errors='coerce').dropna().to_numpy())
        y = np.arange(1, len(x) + 1) / len(x)
        ax.step(x, y, where='post', linewidth=2.2, color=SCENARIO_COLORS[n], label=f"{n}N (n={len(x):,})")
    ax.set_xlim(0, 80)
    ax.set_ylim(0, 1.005)
    ax.set_xlabel("Gateway-referenced local delivery latency $L_{n2g}$ [ms]", fontsize=14)
    ax.set_ylabel("Empirical cumulative probability", fontsize=14)
    ax.tick_params(axis='both', labelsize=12)
    ax.grid(True, alpha=0.25)
    ax.legend(loc='upper right', framealpha=0.9, fontsize=14)
    save_figure_to_all(fig, "ecdf_n2g.png")
    plt.close(fig)

    # Figure 2: Run-level means with old style labels 1N / 3N / 5N.
    fig, ax = plt.subplots(figsize=(9, 6), constrained_layout=True)
    tcrit = 4.3026527299  # Student-t, df=2, two-sided 95%
    xticks = [1, 3, 5]
    xticklabels = ['1N', '3N', '5N']
    for n in xticks:
        g = runs[runs.nodes.eq(n)]
        color = SCENARIO_COLORS[n]
        x_positions = np.linspace(n - 0.12, n + 0.12, len(g))
        ax.scatter(x_positions, g.n2g_mean_ms, s=110, color=color, zorder=3)
        mu = g.n2g_mean_ms.mean()
        sd = g.n2g_mean_ms.std(ddof=1)
        ci = tcrit * sd / math.sqrt(len(g))
        ax.errorbar(n, mu, yerr=ci, fmt='o', markersize=12, color=color, capsize=8, elinewidth=2.0, capthick=2.0, zorder=4)
    ax.set_xlabel("Active sensor nodes", fontsize=16)
    ax.set_ylabel("Run-level mean $L_{n2g}$ [ms]", fontsize=16)
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels, fontsize=16)
    ax.tick_params(axis='y', labelsize=14)
    ax.grid(True, alpha=0.25)
    save_figure_to_all(fig, "run_level_n2g.png")
    plt.close(fig)

    ci_rows = []
    for n, g in runs.groupby('nodes'):
        mu = g.n2g_mean_ms.mean()
        sd = g.n2g_mean_ms.std(ddof=1)
        ci = tcrit * sd / math.sqrt(len(g))
        ci_rows.append({
            'nodes': n,
            'mean_ms': mu,
            'sd_ms': sd,
            'ci95_halfwidth_ms': ci,
            'ci95_low_ms': mu - ci,
            'ci95_high_ms': mu + ci
        })
    pd.DataFrame(ci_rows).to_csv(TABLES / "run_mean_ci95.csv", index=False)

    # Figure 3: old 4-stage throughput plot with final corrected values.
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    width = 0.18
    centers = np.array([1, 3, 5], dtype=float)
    stages = [
        ("TX", "tx_rate_pkt_s"),
        ("Gateway RX", "gateway_rx_rate_pkt_s"),
        ("Gateway published", "gateway_published_rate_pkt_s"),
        ("Stored", "stored_rate_pkt_s"),
    ]
    offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * width
    for offset, (label, col) in zip(offsets, stages):
        means = []
        sds = []
        for n in [1, 3, 5]:
            g = runs[runs.nodes.eq(n)]
            means.append(g[col].mean())
            sds.append(g[col].std(ddof=1))
        ax.bar(centers + offset, means, width, yerr=sds, capsize=4, label=label)
    ax.set_xlabel("Active sensor nodes", fontsize=16)
    ax.set_ylabel("Aggregate throughput [packets/s]", fontsize=16)
    ax.set_xticks(centers)
    ax.set_xticklabels(['1N', '3N', '5N'], fontsize=16)
    ax.tick_params(axis='y', labelsize=14)
    ax.set_ylim(0, 4.05)
    ax.grid(True, axis='y', alpha=0.25)
    ax.legend(loc='upper left', framealpha=0.9, fontsize=14)
    save_figure_to_all(fig, "throughput_sender_vs_database.png")
    # also save under a semantically clearer alternate name
    save_figure_to_all(fig, "throughput_4stage.png")
    plt.close(fig)

    print(runs.to_string(index=False))
    print("\nScenario summary:\n", scenarios.to_string(index=False))


if __name__ == '__main__':
    main()
