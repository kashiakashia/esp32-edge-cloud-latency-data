# Reproducibility package — ESP32/MicroPython bridge-assisted latency campaign

This public package reproduces the quantitative bridge-assisted latency results from the updated experiment campaign.
It includes data exports, preprocessing and analysis scripts, and generated numerical/figure outputs.
Manuscript source files are intentionally not included in this repository.

## Directory structure

- `data/raw/` — original per-run telemetry exports, sender run-summary exports, the full-day InfluxDB export used to recover complete 5-node RUN02/RUN03 sequence ranges, manifests, and gateway console logs.
- `data/processed/` — telemetry records selected for each of the nine 30-min runs after run extraction and duplicate removal.
- `scripts/analyze_campaign.py` — single analysis entry point.
- `outputs/tables/` — run-level, scenario-level, per-node, reliability, throughput, synchronization-quality, and 95% CI tables.
- `outputs/figures/` — figures generated directly by the analysis script.
- `outputs/figures_for_manuscript/` — figure copies prepared for manuscript integration.

## Analysis rules

1. One 30-min run is treated as one independent experimental replicate.
2. Database telemetry is deduplicated by `(node_id, seq)` and the first stored instance is retained.
3. No latency observation is removed solely because it is large.
4. Exact database-visible PDR uses the final sender TX-attempt denominator from each node's run summary.
5. 5N RUN02/RUN03 are reconstructed from the full-day InfluxDB export. For each node, the script uses the final run-summary timestamp and TX denominator, locates the nearest preceding `seq=1`, and extracts that sequence through the final TX value.
6. Gateway raw RX/publication counters contain post-run summary/control traffic and are retained as audit diagnostics. They are not presented as independent telemetry-stage throughput denominators.
7. Packet-level ECDFs are descriptive. Statistical replication is at run level (`n=3` per node-count condition).

## Reproduce

From the package root:

```bash
python scripts/analyze_campaign.py
```

Requirements: Python 3, pandas, numpy, matplotlib.

## Key exact full-run PDR values

- 1 node: 100.000%, 100.000%, 100.000%
- 3 nodes: 99.281%, 99.880%, 99.397%
- 5 nodes: 96.900%, 96.747%, 97.047%

## Important interpretation notes

- The nominal `1 s` sender setting is an inter-cycle sleep, not a fixed 1 Hz period. Sensor acquisition (~273 ms mean), synchronization pauses, payload handling, ESP-NOW transmission, and bounded jitter occur in addition to it, producing the measured ~0.77 packet/s per-node rate.
- `L_n2g` is a gateway-referenced application-level local-delivery metric, not pure radio propagation delay.
- The synchronization interval width `w_theta` is an admissible clock-offset interval width, not a statistical confidence interval.
- The physical placement/radio geometry was held fixed across 1N/3N/5N experiments. The ESP-NOW channel was matched to the gateway Wi-Fi channel for each run.
- Backend-associated timing is architecture- and clock-semantics-specific and is not used as a controlled cloud-provider or node-count scaling benchmark.


## Reproducible two-stage data pipeline

The repository now separates original InfluxDB exports from derived per-run inputs.

1. Prepare the nine campaign run files from the original exports:

```bash
python scripts/prepare_campaign_inputs.py
```

This reads `data/source_exports/` and writes `data/prepared/`, including the complete
5N-RUN02 and 5N-RUN03 telemetry windows recovered from the full-day export. The
preprocessing step retains telemetry duplicates; duplicate removal is deliberately left to
the analysis stage so that the manuscript rule `(node_id, seq) -> keep first` is explicit.

2. Reproduce the cleaned data, tables and manuscript figures:

```bash
python scripts/analyze_campaign.py
```

This reads `data/prepared/`, writes deduplicated telemetry to `data/processed/`, numerical
tables to `outputs/tables/`, and figures to `outputs/figures/` and
`outputs/figures_for_manuscript/`.
