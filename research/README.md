# Multi-Agent Research Workflow

This folder defines a 5-agent research process:
- `empiricalist`: prioritizes observation, data quality, measurement, and replication.
- `theorist`: builds explanatory models and checks conceptual coherence.
- `contrarian`: stress-tests consensus and hunts for neglected alternatives.
- `falsifier`: tries to disprove the strongest claims with strict tests.
- `research-master`: synthesizes all outputs into a decision-grade conclusion.

## Folder Layout

- `agents/`: role prompts and output requirements for each agent.
- `templates/`: normalized report templates.
- `runs/`: per-question research workspaces.
- `setup_run.sh`: creates a new run scaffold.

## Fast Start

```bash
cd research
./setup_run.sh "Your research question"
```

That creates `runs/<timestamp>-<slug>/` with:
- `question.md`
- `subagents/` input + output placeholders
- `master/` synthesis placeholder

## Execution Order

1. Fill `question.md` with scope and constraints.
2. Run four sub-agents independently using prompts in `agents/`.
3. Save each output in `subagents/<agent>.md`.
4. Run `research-master` using all four outputs.
5. Save final synthesis in `master/final.md`.

## Quality Bar

A run is complete only if:
- each sub-agent includes explicit assumptions and confidence,
- disagreement points are surfaced (not averaged away),
- master output contains a final thesis, best evidence, key failure modes, and next tests.
