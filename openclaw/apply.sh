#!/usr/bin/env bash
# Push FieldOps' OpenClaw setup into the 'fieldops' sandbox: network policy, skill, the always-loaded
# TOOLS.md section, then reset the shared session so the agent picks it all up. Safe to re-run.
#   bash openclaw/apply.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
. ~/hackathon-stack/env.sh
sg docker -c "nemoclaw fieldops policy add --from-file openclaw/fieldops-api-policy.yaml --trusted-private-host 172.18.0.1 --yes" | grep -iE "applied|rror" || true
sg docker -c "nemoclaw fieldops skill install openclaw/fieldops-tools" | grep -E "Installed|rror" || true
# Qwen mistakes the skill name for a tool id; TOOLS.md is loaded into every session, so the exact
# 'exec' + curl recipe lives there too.
c=$(sg docker -c "docker ps --format '{{.Names}}'" | grep openshell-default--fieldops | head -1)
sg docker -c "docker exec -i -u sandbox $c sh -c 'f=/sandbox/.openclaw/workspace/TOOLS.md; t=\$(mktemp); sed \"/^## FieldOps (this orchard)/,\\\$d\" \$f > \$t; cat \$t - > \$f; rm \$t'" < openclaw/workspace/TOOLS-fieldops.md
echo "TOOLS.md FieldOps section updated"
sg docker -c "nemoclaw fieldops agent --agent main -m /new" | grep -E "New session" || true
