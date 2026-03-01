# Research Agents

This directory uses a five-agent workflow.

## Sub-Agents

1. `empiricalist`
Focus: data, measurement validity, observed effects, reproducibility.
Output file: `runs/<run-id>/subagents/empiricalist.md`

2. `theorist`
Focus: causal models, mechanism quality, conceptual coherence, predictions.
Output file: `runs/<run-id>/subagents/theorist.md`

3. `contrarian`
Focus: alternative hypotheses, consensus blind spots, underweighted evidence.
Output file: `runs/<run-id>/subagents/contrarian.md`

4. `falsifier`
Focus: disconfirmation tests, kill criteria, claim robustness under failure attempts.
Output file: `runs/<run-id>/subagents/falsifier.md`

## Master Agent

5. `research-master`
Focus: synthesize disagreements into a decision-grade conclusion.
Output file: `runs/<run-id>/master/final.md`

## Execution Protocol

1. Create run: `./setup_run.sh "<question>"`
2. Run four sub-agents in parallel.
3. Ensure each output includes confidence and assumptions.
4. Run `research-master` last on all sub-agent outputs.
5. Keep unresolved disagreements explicit in final synthesis.
