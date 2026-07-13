# Reproducibility package for ESP32 edge--cloud latency analysis

This repository contains the raw InfluxDB CSV exports and Python scripts used to reproduce the quantitative results and plots reported in the manuscript:

**Characterization of Latency Sources in a MicroPython-Based ESP32 Edge--Cloud Sensor Network**

The repository is organized around two measurement groups:

1. **`final_bridge_two_way`** -- the final bridge-assisted campaign with two-way gateway-referenced timestamping.  
   These data reproduce the main numerical results in the manuscript, including the values reported in the abstract, Table 5, Table 6, appendix run-level tables, and Figure 4.

2. **`timestamping_diagnostics/pre_two_way`** -- preliminary runs collected before the final two-way timestamping procedure was introduced.  
   These data are used only for the timestamping-diagnostics comparison in Figure 5, where the earlier timestamping approach is compared with the final two-way approach.

The raw CSV files are not filtered or edited. They are InfluxDB exports kept as measurement records. The scripts perform duplicate removal, sequence-continuity checks, latency calculations, scenario-level aggregation, and figure generation.

---

## Repository structure

```text
.
├── data
│   ├── final_bridge_two_way
│   │   ├── 1node
│   │   │   ├── 30min_1node_run01
│   │   │   │   └── influxdata_2026-06-23T15_24_34Z.csv
│   │   │   ├── 30min_1node_run02
│   │   │   │   └── influxdata_2026-06-23T15_56_38Z.csv
│   │   │   └── 30min_1node_run03
│   │   │       └── influxdata_2026-06-24T09_36_20Z.csv
│   │   │
│   │   ├── 3nodes
│   │   │   ├── 30min_3nodes_run01
│   │   │   │   └── influxdata_2026-06-16T17_24_52Z.csv
│   │   │   ├── 30min_3nodes_run02
│   │   │   │   └── influxdata_2026-06-22T15_21_40Z.csv
│   │   │   └── 30min_3nodes_run03
│   │   │       └── influxdata_2026-06-22T15_54_23Z.csv
│   │   │
│   │   └── 5nodes
│   │       ├── 30min_5nodes_run01
│   │       │   └── influxdata_2026-06-19T13_02_54Z.csv
│   │       ├── 30min_5nodes_run02
│   │       │   └── influxdata_2026-06-19T13_51_53Z.csv
│   │       └── 30min_5nodes_run03
│   │           └── influxdata_2026-06-19T14_28_36Z.csv
│   │
│   └── timestamping_diagnostics
│       └── pre_two_way
│           ├── influxdata_2026-05-25T16_46_06Z.csv
│           ├── influxdata_2026-05-26T14_01_11Z.csv
│           ├── influxdata_2026-06-05T14_26_44Z.csv
│           ├── influxdata_2026-06-07T12_12_05Z.csv
│           ├── influxdata_2026-06-07T12_46_56Z.csv
│           ├── influxdata_2026-06-08T10_05_45Z.csv
│           ├── influxdata_2026-06-09T10_51_33Z.csv
│           └── influxdata_2026-06-09T12_04_13Z.csv
│
├── outputs_expected
│   ├── appendix_run_latency.csv
│   ├── appendix_run_metrics_numeric.csv
│   ├── appendix_run_quality.csv
│   ├── scenario_summary_numeric.csv
│   ├── table5_scenario_quality.csv
│   ├── table6_scenario_latency.csv
│   ├── timestamping_diagnostics_run_metrics.csv
│   ├── timestamping_diagnostics_summary.csv
│   ├── timestamping_diagnostics_verification_report.md
│   ├── verification_report.md
│   └── figures
│       ├── bridge_scaling_summary.pdf
│       ├── bridge_scaling_summary.png
│       ├── timestamping_diagnostics.pdf
│       └── timestamping_diagnostics.png
│
└── scripts
    ├── main_results_and_figure4.py
    └── timestamping_diagnostics.py
```

---

## Data description

### InfluxDB CSV exports

The CSV files are raw exports from InfluxDB. They contain the telemetry records stored in the backend pipeline during each measurement run.

InfluxDB annotated CSV exports usually contain metadata rows before the actual header. The analysis scripts therefore read the files with:

```python
pd.read_csv(path, skiprows=3)
```

Some columns may be empty or only partially populated. This is expected. The InfluxDB bucket and export schema may contain fields from earlier payload versions, diagnostic fields, or fields that were present in the bucket but were not populated by the JSON payload used in a given run. Such columns are retained in the raw CSV files for transparency, but the scripts ignore columns that are not required for the reported analysis.

The most important fields used by the scripts are:

| Column | Meaning |
|---|---|
| `time` | InfluxDB/backend timestamp assigned to the stored record. Used as the backend ingestion timestamp. |
| `node_id` | Identifier of the sensor node that generated the telemetry packet. |
| `seq` | Per-node sequence number used to detect missing packets and duplicates. |
| `n2g_latency_ms` | Node-to-gateway latency already stored in the telemetry record, if present. |
| `g2m_latency_ms` | Gateway-processing latency already stored in the telemetry record, if present. |
| `t_node_unix_ms` | Corrected node-side Unix timestamp, used when latency must be recomputed. |
| `t_gw_rx_unix_ms` | Gateway receive timestamp. |
| `t_gw_tx_unix_ms` | Gateway MQTT publication timestamp. |
| `sync_delay_ms` | Two-way synchronization delay diagnostic, if available. |
| `sync_rtt_ms` | Synchronization round-trip time diagnostic, if available. |
| `node_count` | Metadata field recorded in some runs. This field is not used as the sole source of scenario classification. |

The scripts are designed to tolerate additional columns. If a column is not required for a specific analysis, it is ignored.

### Empty columns and legacy fields

Some CSV exports contain empty columns because the InfluxDB bucket contained fields that were not filled by the telemetry JSON in a particular firmware version or run configuration. For example, a later firmware version may have added synchronization diagnostics, while older runs did not populate these fields. Conversely, some development fields may remain in the bucket/export schema even if they are not used in the final analysis.

These empty or legacy columns are not removed from the raw files. The analysis scripts select only the required fields and leave the raw data unchanged.

---

## Measurement campaigns

### 1. Final bridge-assisted two-way campaign

Folder:

```text
data/final_bridge_two_way/
```

This is the main dataset used for the final quantitative results. It contains three independent 30-minute runs for each tested network size:

- 1 active sensor node,
- 3 active sensor nodes,
- 5 active sensor nodes.

In this campaign, sensor nodes used the final two-way gateway-referenced timestamping procedure. The ESP32 gateway published plaintext MQTT to a local Mosquitto broker, and the local host bridged the stream to EMQX Cloud over TLS. Telegraf on a Raspberry Pi then forwarded the parsed MQTT records to InfluxDB.

These data reproduce:

- the PDR values reported in the abstract;
- the `L_n2g` and `L_gateway` median/p95 values reported in the abstract;
- Table 5;
- Table 6;
- appendix run-level quality and latency tables;
- Figure 4.

One of the three-node CSV exports contains a stale `node_count` metadata value. For this reason, the scripts classify runs using an explicit run manifest, not only the stored `node_count` field. The actual number of node streams is also checked from distinct `node_id` values.

### 2. Timestamping diagnostics campaign

Folder:

```text
data/timestamping_diagnostics/pre_two_way/
```

This folder contains preliminary data collected before the final two-way timestamping procedure was introduced. These runs are used to reproduce the pre-two-way part of Figure 5.

The final two-way values in Figure 5 are not stored in a separate folder. They are taken from the same final bridge-assisted campaign used for Figure 4, Table 5, and Table 6.

The purpose of Figure 5 is to show that the earlier timestamping approach produced artificially inflated apparent node-to-gateway latency. The final two-way timestamping procedure substantially reduced this bias and produced stable `L_n2g` values around 70--80 ms in the evaluated periodic workloads.

---

## Analysis scripts

### `scripts/main_results_and_figure4.py`

This script reproduces the main results from the final bridge-assisted two-way campaign.

It reads the nine CSV files from:

```text
data/final_bridge_two_way/
```

The script performs the following steps:

1. reads each InfluxDB CSV export;
2. converts numeric timing and sequence fields;
3. removes duplicate records using the `(node_id, seq)` pair;
4. retains the first stored instance of a duplicate packet;
5. computes database-visible sequence continuity per node stream;
6. computes unique packet count, missing sequence numbers, duplicate count, database-visible PDR, maximum inter-packet gap, `L_n2g`, `L_gateway`, `L_backend`, `L_total`, and synchronization-delay statistics if available;
7. aggregates run-level medians and 95th percentiles into scenario-level `mean ± SD`;
8. generates Figure 4.

Generated outputs:

```text
outputs_expected/table5_scenario_quality.csv
outputs_expected/table6_scenario_latency.csv
outputs_expected/appendix_run_quality.csv
outputs_expected/appendix_run_latency.csv
outputs_expected/appendix_run_metrics_numeric.csv
outputs_expected/scenario_summary_numeric.csv
outputs_expected/verification_report.md
outputs_expected/figures/bridge_scaling_summary.png
outputs_expected/figures/bridge_scaling_summary.pdf
```

### `scripts/timestamping_diagnostics.py`

This script reproduces the timestamping diagnostic comparison shown in Figure 5.

It reads:

```text
data/timestamping_diagnostics/pre_two_way/
```

for the preliminary pre-two-way runs, and:

```text
data/final_bridge_two_way/
```

for the final two-way reference values.

The script performs the following steps:

1. reads the pre-two-way and final two-way CSV files;
2. removes duplicates using `(node_id, seq)`;
3. computes run-level medians and 95th percentiles of `L_n2g` and `L_gateway`;
4. aggregates results per scenario;
5. generates Figure 5 with a logarithmic y-axis.

Generated outputs:

```text
outputs_expected/timestamping_diagnostics_run_metrics.csv
outputs_expected/timestamping_diagnostics_summary.csv
outputs_expected/timestamping_diagnostics_verification_report.md
outputs_expected/figures/timestamping_diagnostics.png
outputs_expected/figures/timestamping_diagnostics.pdf
```

---

## Metrics

### Database-visible PDR

Packet delivery ratio is computed as a database-visible sequence-continuity metric:

```text
PDR = number of unique packets stored in InfluxDB / expected number of sequence numbers
```

The expected number of sequence numbers is computed independently for each `node_id` stream between the first and last observed `seq` value.

This PDR should not be interpreted as a pure ESP-NOW radio-link PDR. A missing sequence number means that the packet was not visible in the final database export and may have been lost at any stage of the pipeline, including local wireless delivery, gateway queueing, MQTT publication, bridge forwarding, Telegraf handling, or InfluxDB ingestion.

### Latency components

The scripts use the following latency components:

```text
L_n2g     = t_gw_rx - t_node
L_gateway = t_gw_tx - t_gw_rx
L_backend = t_cloud - t_gw_tx
L_total   = t_cloud - t_node
```

where:

- `t_node` is the corrected node-side sender timestamp;
- `t_gw_rx` is the gateway receive timestamp;
- `t_gw_tx` is the gateway MQTT publication timestamp;
- `t_cloud` is represented by the InfluxDB record timestamp.

If `n2g_latency_ms` or `g2m_latency_ms` are already present in the CSV, the scripts use those stored fields. Otherwise, the corresponding metric is recomputed from timestamp columns.

### Duplicate handling

Duplicates are identified using the pair:

```text
(node_id, seq)
```

For latency statistics, the first stored instance is retained. This corresponds to the earliest database-visible instance of a repeated packet.

---

## How to reproduce the results

Install dependencies:

```bash
pip install pandas numpy matplotlib
```

Then run:

```bash
python scripts/main_results_and_figure4.py
python scripts/timestamping_diagnostics.py
```

The scripts write their outputs to:

```text
outputs_expected/
```

The generated files can be compared with the already included files in `outputs_expected/`.

---

## Expected key values

Running `scripts/main_results_and_figure4.py` should reproduce the main values reported in the manuscript abstract:

```text
1 node:
PDR 99.73 ± 0.47%
L_n2g median/p95 69.0/76.3 ms
L_gateway median/p95 6.0/7.0 ms

3 nodes:
PDR 99.82 ± 0.10%
L_n2g median/p95 70.7/77.0 ms
L_gateway median/p95 6.0/7.0 ms

5 nodes:
PDR 99.75 ± 0.03%
L_n2g median/p95 71.0/81.7 ms
L_gateway median/p95 6.0/9.0 ms
```

Running `scripts/timestamping_diagnostics.py` should reproduce the Figure 5 diagnostic values approximately as:

```text
pre_two_way, 1 node:
L_n2g median 723.0 ms
L_n2g p95 2235.7 ms

pre_two_way, 3 nodes:
L_n2g median 681.2 ms
L_n2g p95 2180.8 ms

pre_two_way, 5 nodes:
L_n2g median 714.0 ms
L_n2g p95 2174.5 ms

final_two_way, 1 node:
L_n2g median 69.0 ms
L_n2g p95 76.3 ms

final_two_way, 3 nodes:
L_n2g median 70.7 ms
L_n2g p95 77.0 ms

final_two_way, 5 nodes:
L_n2g median 71.0 ms
L_n2g p95 81.7 ms
```

Small numerical differences can occur if a different pandas/numpy version changes percentile interpolation behavior. The scripts use pandas `quantile(0.95)` for the 95th percentile.

---

## Notes on raw data integrity

The files in `data/` are raw InfluxDB CSV exports. They should not be edited manually.

The processed files in `outputs_expected/` are derived outputs generated by the scripts. If the scripts are re-run, these files may be overwritten.
