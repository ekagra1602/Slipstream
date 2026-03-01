#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: ./setup_run.sh \"Your research question\""
  exit 1
fi

QUESTION="$*"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SLUG="$(echo "$QUESTION" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//' | cut -c1-60)"
RUN_DIR="runs/${TIMESTAMP}-${SLUG}"

mkdir -p "${RUN_DIR}/subagents" "${RUN_DIR}/master"
cp templates/question-template.md "${RUN_DIR}/question.md"

cat >> "${RUN_DIR}/question.md" <<EOF2

## Working Prompt

${QUESTION}
EOF2

for agent in empiricalist theorist contrarian falsifier; do
  cp templates/subagent-output.md "${RUN_DIR}/subagents/${agent}.md"
done

cp templates/master-output.md "${RUN_DIR}/master/final.md"

cat > "${RUN_DIR}/RUNBOOK.md" <<EOF2
# Runbook

1. Use the prompt guide in ../../agents/empiricalist.md and fill subagents/empiricalist.md.
2. Use the prompt guide in ../../agents/theorist.md and fill subagents/theorist.md.
3. Use the prompt guide in ../../agents/contrarian.md and fill subagents/contrarian.md.
4. Use the prompt guide in ../../agents/falsifier.md and fill subagents/falsifier.md.
5. Use ../../agents/research-master.md to synthesize into master/final.md.
EOF2

echo "Created: ${RUN_DIR}"
echo "Next: fill ${RUN_DIR}/question.md, then run all 4 sub-agent analyses in parallel."
