# Benchmark v2 Summary

- runs: 20
- ok: 20
- judged_pass: 9
- judged_pass_rate_pct: 45.0
- judged_fail: 11
- avg_total_tokens: 0.0
- avg_estimated_usd_cost: 0.0
- total_estimated_usd_cost: 0.0
- avg_steps: 4.8
- median_steps: 4.5
- min_steps: 4
- max_steps: 7
- avg_duration_s: 36.18
- median_duration_s: 35.84
- p90_duration_s: 41.54
- min_duration_s: 28.79
- max_duration_s: 41.95
- first_5_avg_duration_s: 35.84
- last_5_avg_duration_s: 35.74
- duration_delta_last_minus_first_s: -0.1
- first_5_avg_steps: 5.2
- last_5_avg_steps: 4.8
- steps_delta_last_minus_first: -0.4
- confidence_start: 0.382
- confidence_end: 0.316
- confidence_peak: 0.499
- confidence_delta: -0.066
- mode: same
- domains: google.com
- backend: mongo

## Judge Fail Reasons
1. The agent provided a hallucinated or outdated result ('IGDMBot...') that does not match the actual first result visible in the search results screenshot ('NEW Clawdbot AI Browser Agent...').
2. The agent provided a result title that does not match the live search results shown in the screenshots, likely relying on outdated cached information. It failed to actually extract the title from the current page state.
3. The agent reported an incorrect search result title that did not match the actual content shown in the browser. It appears to have relied on a cached 'past successful result' rather than reading the live page content, which showed 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?' as the first resu
4. The agent hallucinated the final result by using outdated information from a tool suggestion instead of reading the actual results on the page. The title it provided ('IGDMBot...') does not appear in the search results shown in the screenshots.
5. The agent reported an incorrect search result title ('IGDMBot...') that was not present as the first result on the page. It appears to have relied on cached/past data from its tool rather than extracting the actual title visible in the search results ('NEW Clawdbot AI Browser Agent...').
6. The agent provided a search result title ('IGDMBot') that does not appear in the search results shown in the screenshots, effectively hallucinating or using outdated cached data instead of the live page content.
7. The agent provided a search result title from its internal memory/shortcut ('IGDMBot') which does not match the actual first result visible in the screenshots ('NEW Clawdbot AI Browser Agent').
8. The agent reported a result title ('IGDMBot...') that does not match the actual first result shown in the search results screenshots ('NEW Clawdbot AI Browser Agent...'). It appears the agent relied on a suggested shortcut from its internal tools instead of extracting the information from the curren
9. The agent provided an incorrect result title that did not match the actual search results shown in the screenshots. It likely hallucinated the answer or relied on outdated cached information from a previous run instead of reading the current page.
10. The agent reported an incorrect result by relying on cached/suggested data instead of the actual content on the page. The title it provided ('IGDMBot...') is not the first result shown in the search screenshots.
11. The agent provided a search result title ('IGDMBot...') that does not appear in the search results shown in the screenshot. It likely hallucinated the answer or relied on outdated cached data rather than the actual content of the page it loaded.

## Files
- CSV: `benchmarks/benchmark_v2/20260301T105758Z/results.csv`
- JSONL: `benchmarks/benchmark_v2/20260301T105758Z/results.jsonl`
