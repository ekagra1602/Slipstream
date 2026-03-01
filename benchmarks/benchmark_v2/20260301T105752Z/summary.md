# Benchmark v2 Summary

- runs: 20
- ok: 20
- judged_pass: 6
- judged_pass_rate_pct: 30.0
- judged_fail: 14
- avg_total_tokens: 0.0
- avg_estimated_usd_cost: 0.0
- total_estimated_usd_cost: 0.0
- avg_steps: 4.8
- median_steps: 5.0
- min_steps: 4
- max_steps: 7
- avg_duration_s: 35.53
- median_duration_s: 34.13
- p90_duration_s: 42.25
- min_duration_s: 28.02
- max_duration_s: 52.11
- first_5_avg_duration_s: 35.79
- last_5_avg_duration_s: 38.99
- duration_delta_last_minus_first_s: 3.2
- first_5_avg_steps: 5.2
- last_5_avg_steps: 4.8
- steps_delta_last_minus_first: -0.4
- confidence_start: 0.275
- confidence_end: 0.327
- confidence_peak: 0.475
- confidence_delta: 0.052
- mode: same
- domains: google.com
- backend: mongo

## Judge Fail Reasons
1. The agent reported a result ('IGDMBot...') that was not actually the first result on the page shown in the screenshots ('NEW Clawdbot...'). It relied on cached/past information rather than extracting the current data from the browser, leading to an incorrect answer.
2. The agent provided the incorrect title for the first search result. Based on the screenshots, the first result was a video titled 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?', but the agent reported 'IGDMBot - DM Automation Bot - Chrome Web Store', which matches its internal tool's 'Past succ
3. The agent provided an incorrect result title. It used a cached result from a previous similar task instead of extracting the actual first result visible on the current search results page, which were YouTube videos.
4. The agent provided an incorrect result title ('IGDMBot') by relying on cached/past data instead of the actual search results shown in the screenshot, where the first title was 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?'.
5. The agent provided a hallucinated or outdated search result title that did not match the actual first result shown in the search results on the page. It relied on a suggested shortcut from its tool instead of extracting the data from the live browser state.
6. The agent provided an incorrect result title by relying on a 'past successful result' from its internal tool rather than extracting the actual information from the current page. The screenshot shows the first result was 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?', while the agent reported 'I
7. The agent reported a hallucinated search result ('IGDMBot') instead of the actual first result visible on the screen ('NEW Clawdbot AI Browser Agent' or relevant video titles). It failed to verify the content of the page after the search and relied on incorrect cached data.
8. The agent provided an incorrect result title that was not present as the first result in the search page screenshots. It appears to have hallucinated the answer based on a 'past successful result' suggestion from its tools rather than extracting the information from the current page.
9. The agent provided a cached result from its internal memory rather than extracting the actual first result from the search page. The screenshots show that the first result on the page was not 'IGDMBot', making the final answer incorrect.
10. The agent reported a title that does not exist in the current search results shown in the screenshots, likely relying on an incorrect internal suggestion/shortcut instead of the actual page content.
11. The agent provided an incorrect title for the first search result. It relied on internal cached information from a previous run instead of extracting the actual first result visible on the current search results page, which was 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?'.
12. The agent reported a title ('IGDMBot - DM Automation Bot') that was not the first result on the search page. The actual first result visible in the screenshots was 'NEW Clawdbot AI Browser Agent: Automate ANYTHING?'. The agent appears to have relied on cached/suggested information rather than extrac
13. The agent provided an incorrect result title that did not match the actual search results shown in the screenshots. It appears to have relied on a 'past successful result' from its internal tool rather than extracting the information from the current page state.
14. The agent reported a title ('IGDMBot...') that does not appear in the search results shown in the screenshots. The actual first results were YouTube videos related to 'Clawdbot' and other automation tools. The agent seems to have used a shortcut answer from its tool history instead of reading the li

## Files
- CSV: `benchmarks/benchmark_v2/20260301T105752Z/results.csv`
- JSONL: `benchmarks/benchmark_v2/20260301T105752Z/results.jsonl`
