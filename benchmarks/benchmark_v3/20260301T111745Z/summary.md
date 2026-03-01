# Benchmark v3 Summary

- runs: 25
- ok: 25
- judged_pass: 21
- judged_pass_rate_pct: 84.0
- judged_fail: 4
- avg_total_tokens: 0.0
- avg_estimated_usd_cost: 0.0
- total_estimated_usd_cost: 0.0
- avg_steps: 14.72
- median_steps: 14
- min_steps: 10
- max_steps: 22
- avg_duration_s: 175.71
- median_duration_s: 173.31
- p90_duration_s: 210.15
- min_duration_s: 127.96
- max_duration_s: 250.11
- first_5_avg_duration_s: 157.65
- last_5_avg_duration_s: 192.52
- duration_delta_last_minus_first_s: 34.87
- first_5_avg_steps: 12.8
- last_5_avg_steps: 16.6
- steps_delta_last_minus_first: 3.8
- confidence_start: 0.0
- confidence_end: 0.12
- confidence_peak: 0.449
- confidence_delta: 0.12
- mode: same
- domains: walmart.com
- backend: mongo

## Judge Fail Reasons
1. The agent selected a USB C hub with only 49 reviews, failing the requirement for at least 100 reviews. It also failed to sufficiently search for the cheapest item that actually met all the specified constraints.
2. The agent failed to return the output in the requested 7-line format. Additionally, the agent did not extract the product titles and unit prices directly from the cart page view as required, instead relying on pre-cached or hallucinated data that didn't perfectly match the final cart state (e.g., ig
3. The agent selected a USB C hub with only 49 reviews, failing the requirement for at least 100 reviews. Additionally, the agent appeared to rely on a 'past successful result' template rather than correctly navigating and extracting the actual data from the live session.
4. The agent failed to extract the actual data from the cart page and instead returned a 'Past successful result' provided by a tool, which contained outdated or incorrect information. Specifically, the hub price and product description in the final output did not match the items actually added to the

## Files
- CSV: `benchmarks/benchmark_v3/20260301T111745Z/results.csv`
- JSONL: `benchmarks/benchmark_v3/20260301T111745Z/results.jsonl`
