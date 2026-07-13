# Timestamping diagnostics verification report

This report is generated automatically by `scripts/reproduce_timestamping_diagnostics.py`.

## Scenario-level values used for Figure 5

### pre_two_way

- 1 node: L_n2g median 723.0 ± 4.2 ms; L_n2g p95 2235.7 ± 64.1 ms; L_gateway median 4.0 ± 0.0 ms; L_gateway p95 5.0 ± 0.0 ms.
- 3 nodes: L_n2g median 681.2 ± 61.7 ms; L_n2g p95 2180.8 ± 52.7 ms; L_gateway median 4.0 ± 0.0 ms; L_gateway p95 5.3 ± 0.6 ms.
- 5 nodes: L_n2g median 714.0 ± 50.8 ms; L_n2g p95 2174.5 ± 5.8 ms; L_gateway median 4.0 ± 0.0 ms; L_gateway p95 5.0 ± 0.0 ms.

### final_two_way

- 1 node: L_n2g median 69.0 ± 1.7 ms; L_n2g p95 76.3 ± 0.6 ms; L_gateway median 6.0 ± 0.0 ms; L_gateway p95 7.0 ± 0.0 ms.
- 3 nodes: L_n2g median 70.7 ± 0.6 ms; L_n2g p95 77.0 ± 0.0 ms; L_gateway median 6.0 ± 0.0 ms; L_gateway p95 7.0 ± 0.0 ms.
- 5 nodes: L_n2g median 71.0 ± 0.0 ms; L_n2g p95 81.7 ± 0.6 ms; L_gateway median 6.0 ± 0.0 ms; L_gateway p95 9.0 ± 0.0 ms.

## Run-level files

- PRE-1N-RUN01: timestamping_diagnostics/pre_two_way/influxdata_2026-05-25T16_46_06Z.csv (unique records: 554, node streams: 1, PDR: 100.000%).
- PRE-1N-RUN02: timestamping_diagnostics/pre_two_way/influxdata_2026-05-26T14_01_11Z.csv (unique records: 532, node streams: 1, PDR: 95.170%).
- PRE-3N-RUN01: timestamping_diagnostics/pre_two_way/influxdata_2026-06-05T14_26_44Z.csv (unique records: 1635, node streams: 3, PDR: 93.750%).
- PRE-3N-RUN02: timestamping_diagnostics/pre_two_way/influxdata_2026-06-07T12_12_05Z.csv (unique records: 1590, node streams: 3, PDR: 97.726%).
- PRE-3N-RUN03: timestamping_diagnostics/pre_two_way/influxdata_2026-06-07T12_46_56Z.csv (unique records: 1576, node streams: 3, PDR: 96.746%).
- PRE-5N-RUN01: timestamping_diagnostics/pre_two_way/influxdata_2026-06-08T10_05_45Z.csv (unique records: 2687, node streams: 5, PDR: 96.794%).
- PRE-5N-RUN02: timestamping_diagnostics/pre_two_way/influxdata_2026-06-09T10_51_33Z.csv (unique records: 2579, node streams: 5, PDR: 94.573%).
- PRE-5N-RUN03: timestamping_diagnostics/pre_two_way/influxdata_2026-06-09T12_04_13Z.csv (unique records: 2630, node streams: 5, PDR: 96.798%).
- FINAL-1N-RUN01: final_bridge_two_way/1node/30min_1node_run01/influxdata_2026-06-23T15_24_34Z.csv (unique records: 1346, node streams: 1, PDR: 100.000%).
- FINAL-1N-RUN02: final_bridge_two_way/1node/30min_1node_run02/influxdata_2026-06-23T15_56_38Z.csv (unique records: 1346, node streams: 1, PDR: 100.000%).
- FINAL-1N-RUN03: final_bridge_two_way/1node/30min_1node_run03/influxdata_2026-06-24T09_36_20Z.csv (unique records: 1332, node streams: 1, PDR: 99.181%).
- FINAL-3N-RUN01: final_bridge_two_way/3nodes/30min_3nodes_run01/influxdata_2026-06-16T17_24_52Z.csv (unique records: 4032, node streams: 3, PDR: 99.926%).
- FINAL-3N-RUN02: final_bridge_two_way/3nodes/30min_3nodes_run02/influxdata_2026-06-22T15_21_40Z.csv (unique records: 4035, node streams: 3, PDR: 99.728%).
- FINAL-3N-RUN03: final_bridge_two_way/3nodes/30min_3nodes_run03/influxdata_2026-06-22T15_54_23Z.csv (unique records: 4025, node streams: 3, PDR: 99.802%).
- FINAL-5N-RUN01: final_bridge_two_way/5nodes/30min_5nodes_run01/influxdata_2026-06-19T13_02_54Z.csv (unique records: 6679, node streams: 5, PDR: 99.761%).
- FINAL-5N-RUN02: final_bridge_two_way/5nodes/30min_5nodes_run02/influxdata_2026-06-19T13_51_53Z.csv (unique records: 6695, node streams: 5, PDR: 99.762%).
- FINAL-5N-RUN03: final_bridge_two_way/5nodes/30min_5nodes_run03/influxdata_2026-06-19T14_28_36Z.csv (unique records: 6694, node streams: 5, PDR: 99.717%).

The figure itself uses the scenario-level mean of run-level medians and run-level 95th percentiles.
