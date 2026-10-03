
## FieldOps (this orchard) — read this before any pest, trap, block or photo request

`fieldops-tools` is a **skill, not a tool**. Never call `fieldops-tools`, `skill-creator` or
`tool_call` as a tool id. Every FieldOps action is one shell command run with the **`exec`** tool:

    tool_call  id="exec"  args={"command": "<the curl command below>"}

**A trap photo arrives** (any image): count it, then reply. Run these with `exec`, in order:

1. `curl -s --data-binary @"<the image path you were given>" "http://172.18.0.1:8765/count?trap_id=<trap id or unknown-trap>"`
2. From its JSON take `summary`, `total_pests`, `block_report.headline`, `block_report.detail`,
   `annotated_file`, `annotated_url`.
3. `mkdir -p /sandbox/.openclaw/workspace/fieldops && curl -s -o "/sandbox/.openclaw/workspace/fieldops/<annotated_file>" "http://172.18.0.1:8765<annotated_url>"`
4. Reply, short: the counts (one line per species), the block headline and detail, and **end with**
   `![pests counted](/sandbox/.openclaw/workspace/fieldops/<annotated_file>)` — Telegram sends it as a photo.

Never count insects by looking at the image yourself; the numbers come only from `/count`.

**Questions** (also via `exec` + `curl -s`): whole farm → `http://172.18.0.1:8765/farm`;
one block → `http://172.18.0.1:8765/block?block=c`; degree-days → `/degree_days?block=c`;
recent catches → `/counts?block=c&days=14`. Quote the numbers; never compute your own.
More detail: `/sandbox/.openclaw/workspace/skills/fieldops-tools/SKILL.md`.
