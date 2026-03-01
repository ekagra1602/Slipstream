# Benchmark v3 Summary

- runs: 25
- ok: 25
- judged_pass: 24
- judged_pass_rate_pct: 96.0
- judged_fail: 1
- avg_total_tokens: 0.0
- avg_estimated_usd_cost: 0.0
- total_estimated_usd_cost: 0.0
- avg_steps: 12.4
- median_steps: 12
- min_steps: 8
- max_steps: 27
- avg_duration_s: 161.27
- median_duration_s: 151.13
- p90_duration_s: 186.61
- min_duration_s: 124.68
- max_duration_s: 294.63
- first_5_avg_duration_s: 175.65
- last_5_avg_duration_s: 151.71
- duration_delta_last_minus_first_s: -23.94
- first_5_avg_steps: 14.6
- last_5_avg_steps: 12.0
- steps_delta_last_minus_first: -2.6
- confidence_start: 0.0
- confidence_end: 0.12
- confidence_peak: 0.45
- confidence_delta: 0.12
- mode: same
- domains: walmart.com
- backend: mongo

## Judge Fail Reasons
1. The agent provided a final output based on a 'Past successful result' suggestion from a tool rather than extracting the information from the current page. Additionally, the final screenshot of the cart shows that the item details and prices failed to load/render, making it impossible for the agent t

## Files
- CSV: `benchmarks/benchmark_v3/20260301T111747Z/results.csv`
- JSONL: `benchmarks/benchmark_v3/20260301T111747Z/results.jsonl`
