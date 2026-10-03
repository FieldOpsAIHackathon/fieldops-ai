---
name: safe-push
description: Pull and reconcile with the remote before every git push. Use whenever the user asks to push, "push it out", "ship it", "send it up", or when you are about to run `git push` for any reason. Also use before opening a PR from a branch that others commit to. Prevents pushing work that silently contradicts what teammates landed while you were writing.
---

# safe-push

Never push without pulling first. On a shared branch, the remote moves while you work, and the
cost is not a merge conflict — git catches those. The cost is the **silent** contradiction: your
commit applies cleanly on top of a teammate's and still disagrees with it. A doc that cites a path
they renamed. A threshold your plan says is 3 and their config says 2. Both commits are "correct";
together they mislead the next person who reads them.

Work through the steps in order. Do not skip to step 7.

## 1. Know what is uncommitted

```bash
git status --short
```

Decide what belongs in this push. Uncommitted work from an unrelated task stays out of it.

## 2. Fetch and look before you touch anything

```bash
git fetch origin
git log --oneline HEAD..origin/main        # what landed while you worked
git diff --stat HEAD origin/main           # which files it touched
```

If nothing is incoming, go to step 6.

## 3. Read the incoming work

**This is the step that earns the skill.** Do not treat a clean fast-forward as a green light.
For every incoming commit that touches territory your change describes or depends on, read it:

```bash
git show <sha> -- <path>
```

Pay attention when the remote added or changed:

- **A contract, schema, or interface spec** — your code or docs may now describe a different shape.
- **Config files** — key names and threshold values your work cites may have moved.
- **Files you reference by path** — a rename makes your links dead.
- **Modules you planned to write** — someone may have built it already, differently.

## 4. Pull

With a clean tree, fast-forward:

```bash
git pull --rebase origin main
```

With uncommitted work you want to keep, either commit it first, or stash only the files in question
and restore them after:

```bash
git stash push -m "wip" <paths>
git pull --rebase origin main
git stash pop
```

Prefer committing over stashing when the work is coherent — a stash pop during a conflict is a bad
place to be.

## 5. Reconcile before you push, not after

If step 3 found a disagreement, resolve it now:

- **Your work is stale** — update it to match what landed. Fix paths, key names, values.
- **Their work and a frozen contract disagree** — do not silently pick a side in someone else's
  module. Document the divergence plainly (a short table beats a paragraph), flag it to the user,
  and let the owner choose.
- **Your plan described something now built differently** — describe what exists, not what you
  imagined.

The rule: **never push a document or comment that is wrong about the repo it ships in.**

## 6. Verify what you are about to claim

If your change documents a command, run it. If it touches code, run the self-test or the suite.
Do not put a command in a README you have not executed on the current tree.

## 7. Push, then confirm

```bash
git fetch -q origin && git log --oneline HEAD..origin/main   # anything land during steps 3-6?
git push origin main
git status -sb
```

A busy repo can move again while you reconcile. If it did, return to step 3 — the second pass is
usually quick.

## 8. Report honestly

Give the user the sha range (`abc1234..def5678`), say what you reconciled and why, and name
anything you found but deliberately did not fix. If you discovered a divergence between a contract
and an implementation, surface it — that is usually worth more to them than the push itself.

## Branch note

These steps say `main` because that is the common case. Use the actual upstream:

```bash
git rev-parse --abbrev-ref --symbolic-full-name @{u}
```

If the current branch is the repo's default branch and the change is not trivial, ask whether to
branch first — unless the user has already said to push straight to it in this session.

## What this skill is not

It is advisory. You have to remember to follow it. If the user wants pulling before pushing
*enforced* rather than remembered, that is a `PreToolUse` hook on `Bash` that inspects the command
for `git push` and blocks when the local branch is behind its upstream. Offer that if they ask for
a guarantee.
