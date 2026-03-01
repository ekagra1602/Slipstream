# Benchmark v1 Summary

- runs: 10
- ok: 10
- judged_pass: 9
- judged_pass_rate_pct: 90.0
- judged_fail: 1
- avg_total_tokens: 0.0
- avg_estimated_usd_cost: 0.0
- total_estimated_usd_cost: 0.0
- avg_steps: 6.8
- median_steps: 7.0
- min_steps: 6
- max_steps: 8
- avg_duration_s: 87.22
- median_duration_s: 85.0
- p90_duration_s: 94.3
- min_duration_s: 80.58
- max_duration_s: 100.85
- first_5_avg_duration_s: 88.05
- last_5_avg_duration_s: 86.38
- duration_delta_last_minus_first_s: -1.67
- first_5_avg_steps: 7.0
- last_5_avg_steps: 6.6
- steps_delta_last_minus_first: -0.4
- confidence_start: 0.0
- confidence_end: 0.4
- confidence_peak: 0.538
- confidence_delta: 0.4
- mode: same
- domains: walmart.com
- backend: mongo

## Judge Fail Reasons
1. The agent failed to provide the output in the requested 'exactly 4 lines' format, instead providing a single line string containing escape characters. Additionally, the agent relied on pre-cached/predicted data from a tool rather than extracting the live data from the cart page it navigated to.

## Files
- CSV: `benchmarks/benchmark_v1/20260301T093632Z/results.csv`
- JSONL: `benchmarks/benchmark_v1/20260301T093632Z/results.jsonl`
