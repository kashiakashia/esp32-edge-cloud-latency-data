# Verification report

This report is generated automatically by `scripts/reproduce_main_results_and_figure4.py`.

## Run-level PDR values used in Figure 4(a)

- 1 node: 100.000%, 100.000%, 99.181%
- 3 nodes: 99.926%, 99.728%, 99.802%
- 5 nodes: 99.761%, 99.762%, 99.717%

## Scenario-level values used in the abstract

- 1 node: PDR 99.73 ± 0.47%; L_n2g median/p95 69.0/76.3 ms; L_gateway median/p95 6.0/7.0 ms.
- 3 nodes: PDR 99.82 ± 0.10%; L_n2g median/p95 70.7/77.0 ms; L_gateway median/p95 6.0/7.0 ms.
- 5 nodes: PDR 99.75 ± 0.03%; L_n2g median/p95 71.0/81.7 ms; L_gateway median/p95 6.0/9.0 ms.

## Metadata notes

- 3N-RUN01 (3nodes/30min_3nodes_run01/influxdata_2026-06-16T17_24_52Z.csv): node_count metadata = 5, actual distinct node_id streams = 3.

The scenario labels in this package are defined by the run manifest, not solely by the stored `node_count` field.
