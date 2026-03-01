# Benchmark v1 Summary

- runs: 10
- ok: 10
- judged_pass: 9
- judged_pass_rate_pct: 90.0
- judged_fail: 1
- avg_total_tokens: 0.0
- avg_estimated_usd_cost: 0.0
- total_estimated_usd_cost: 0.0
- avg_steps: 10.3
- median_steps: 9.5
- min_steps: 5
- max_steps: 18
- avg_duration_s: 125.05
- median_duration_s: 110.07
- p90_duration_s: 178.34
- min_duration_s: 77.14
- max_duration_s: 184.19
- first_5_avg_duration_s: 89.06
- last_5_avg_duration_s: 161.03
- duration_delta_last_minus_first_s: 71.97
- first_5_avg_steps: 6.8
- last_5_avg_steps: 13.8
- steps_delta_last_minus_first: 7.0
- confidence_start: 0.525
- confidence_end: 0.668
- confidence_peak: 0.718
- confidence_delta: 0.143
- mode: same
- domains: walmart.com
- backend: mongo

## Judge Fail Reasons
1. The agent failed to adhere to the constraint of extracting all values from the cart page only. Rating and review count were not available on the cart page (confirmed by the agent's own failed search of the page text), yet the agent included them in the final output by using information from previous

## Files
- CSV: `benchmarks/benchmark_v1/20260301T085710Z/results.csv`
- JSONL: `benchmarks/benchmark_v1/20260301T085710Z/results.jsonl`
