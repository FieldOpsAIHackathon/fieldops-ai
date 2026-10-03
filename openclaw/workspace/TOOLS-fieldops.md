
## FieldOps (this orchard) — read this before any pest, trap, block or photo request

`fieldops-tools` is a **skill, not a tool**. Never call `fieldops-tools`, `skill-creator` or
`tool_call` as a tool id. Every FieldOps action is one shell command run with the **`exec`** tool:

    tool_call  id="exec"  args={"command": "<the curl command below>"}

**A trap photo arrives** (any image). The only inputs are **the image** and **the section name the
user gave with it** (e.g. "block C", "section C trap 4"). Nothing else: do not call `/farm`, `/status`,
`/counts` or `/degree_days` for a photo, and do not mention other blocks.

1. Trap id: section C → `block-c-01`; section C trap 4 → `block-c-04`; no section given → `unknown-trap`.
   Run with `exec`:
   `curl -s --data-binary @"<the image path you were given>" "http://172.18.0.1:8765/count?trap_id=<trap id>"`
2. From its JSON take `summary`, `total_pests`, `annotated_file`, `annotated_url`, and — only if a
   section was given — `block_report.headline` and `block_report.detail` (that one section only).
3. `mkdir -p /sandbox/.openclaw/workspace/fieldops && curl -s -o "/sandbox/.openclaw/workspace/fieldops/<annotated_file>" "http://172.18.0.1:8765<annotated_url>"`
4. Reply, short and nothing more:
   - one line per species with its count, and the total;
   - if a section was given: that section's headline and detail (two lines);
   - if no section was given: one line asking which section the trap is in;
   - **end with** `![](/sandbox/.openclaw/workspace/fieldops/<annotated_file>)` — Telegram sends it as a photo.

Never count insects by looking at the image yourself; the numbers come only from `/count`.

**Questions** (also via `exec` + `curl -s`). Whole farm (`http://172.18.0.1:8765/farm`) **only when the user
explicitly asks about the whole farm**;
one block → `http://172.18.0.1:8765/block?block=c`; degree-days → `/degree_days?block=c`;
recent catches → `/counts?block=c&days=14`. Quote the numbers; never compute your own.
More detail: `/sandbox/.openclaw/workspace/skills/fieldops-tools/SKILL.md`.
