# Benchmark v2 Summary

- runs: 20
- ok: 20
- judged_pass: 6
- judged_pass_rate_pct: 30.0
- judged_fail: 14
- avg_total_tokens: 0.0
- avg_estimated_usd_cost: 0.0
- total_estimated_usd_cost: 0.0
- avg_steps: 4.95
- median_steps: 5.0
- min_steps: 4
- max_steps: 9
- avg_duration_s: 36.62
- median_duration_s: 33.44
- p90_duration_s: 45.28
- min_duration_s: 27.74
- max_duration_s: 60.78
- first_5_avg_duration_s: 39.04
- last_5_avg_duration_s: 39.71
- duration_delta_last_minus_first_s: 0.67
- first_5_avg_steps: 5.0
- last_5_avg_steps: 5.8
- steps_delta_last_minus_first: 0.8
- confidence_start: 0.0
- confidence_end: 0.321
- confidence_peak: 0.512
- confidence_delta: 0.321
- mode: same
- domains: google.com
- backend: mongo

## Judge Fail Reasons
1. The agent reported a first result title ('IGDMBot...') that is not visible in the provided screenshots of the search results. The screenshots show a 'Videos' section at the top, and the agent failed to accurately capture the actual first result visible on the page.
2. The agent provided a result title ('IGDMBot - DM Automation Bot - Chrome Web Store') that was not present in the search results shown in the screenshots, relying instead on incorrect cached data from a previous run. The actual first results visible were video titles from a YouTube carousel.
3. The agent provided a result title ('IGDMBot...') that does not appear in the actual search results shown in the screenshots (which show 'NEW Clawdbot AI Browser Agent...' as the top result). It seems the agent relied on a suggested past result instead of the live data.
4. The agent provided an incorrect result title that did not match the actual search results shown in the screenshots. It appears to have relied on a cached or suggested answer ('IGDMBot') rather than extracting the title from the live page, where the first title was 'NEW Clawdbot AI Browser Agent: Aut
5. The agent hallucinated the result by relying on a cached response from a tool instead of reading the actual search results on the page. The reported title 'IGDMBot - DM Automation Bot - Chrome Web Store' does not match the actual first result shown in the screenshots, which was a video titled 'NEW C
6. The agent provided an incorrect result title by relying on a 'past successful result' shortcut from a tool instead of extracting the title from the actual page. The real first result shown in the screenshot was 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?', whereas the agent reported 'IGDMBot.
7. The agent provided an incorrect result title ('IGDMBot...') based on cached data or a previous run, whereas the actual first result on the page was 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?'.
8. The agent provided an incorrect result title that did not match the live search results shown in the screenshots, likely by relying on cached information from a previous run rather than the actual browser state.
9. The agent reported a result ('IGDMBot') that was not present as the first result on the live search page shown in the screenshots, effectively hallucinating based on internal suggestions instead of extracting actual data from the page.
10. The agent reported a search result title ('IGDMBot...') that does not match the actual first results visible in the search screenshots, likely due to over-reliance on a tool's past result hint rather than live extraction.
11. The agent provided an incorrect search result title that does not match the content displayed in the search results screenshot. It likely hallucinated the result based on cached data rather than extracting it from the live page.
12. The agent provided a search result title ('IGDMBot...') that did not match the actual first result shown on the page ('NEW Clawdbot AI Browser Agent...'). It appears to have relied on incorrect cached information from a tool rather than observing the actual page content.
13. The agent provided a search result title ('IGDMBot...') that was not present on the actual search results page shown in the screenshots, effectively hallucinating the answer based on a tool's suggestion rather than reading the page.
14. The agent provided an incorrect search result title that did not match the actual content shown in the browser. It likely hallucinated the answer based on a 'past successful result' suggested by its tool instead of extracting the real data from the current page.

## Files
- CSV: `benchmarks/benchmark_v2/20260301T105745Z/results.csv`
- JSONL: `benchmarks/benchmark_v2/20260301T105745Z/results.jsonl`
