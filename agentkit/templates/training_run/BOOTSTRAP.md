# Bootstrap

You are the **learning agent** in an agentkit training run. Your job is to **design and implement a learning algorithm** — a process that consumes training samples, uses feedback to modify yourself, periodically validates your progress without overfitting, and accumulates a useful set of skills/notes/code/data in *this directory* over time.

This document is the canonical specification of your job. It tells you what the framework guarantees, what surface you have to work with, and what counts as a valid learning algorithm. Everything else — *how* you reflect, *what* you store, *when* you validate, whether you spawn subagents — is up to you.

## What is in this directory

- `BOOTSTRAP.md` — this file.
- `CLAUDE.md` — short identity doc, auto-loaded by Claude Code on session start.
- `.gitignore` — ignores `.agentkit/` and python clutter.
- `.agentkit/state.json` — framework-owned state. Read it when you need to. Do **not** edit it directly; mutate it only by calling agentkit CLI commands. It records: which training ids you have consumed and skipped, the path to the task source (`task_path`), the val history with git shas.
- **Everything else** is yours. Write skills, learning notes, scripts, helpers, the `answer` script, whatever your algorithm needs.

## What is NOT in this directory

The **task source** lives elsewhere — at the absolute path `task_path` in `.agentkit/state.json`. **You must not read it.** That path contains the data loading and scoring code, which would let you extract gold answers if you peeked. The framework loads the task on your behalf when you call `agentkit next-train`, `agentkit submit-train`, etc. You only ever see prompts and feedback through the CLI; you never touch the underlying dataset.

## What you give the framework

1. An executable **`answer`** script in this directory. It is invoked with a task prompt on stdin and must print an answer on stdout that matches the task's answer format (run `agentkit task-info` to see the format spec). This script is your *deployed* artifact — whatever you learn must change how this script behaves, otherwise you have not learned anything measurable.
2. **Git commits**, periodically. Validation will only run when this dir's git HEAD has actually changed since the last validation — see "Validation gating" below.

## What a valid learning algorithm looks like

1. **It is written down in this workspace.** Someone forking this dir should be able to understand how you learn just by reading the files you've committed. Don't keep the algorithm in your head — write it down (e.g. in `LEARNING_ALGORITHM.md`), and update it as you refine it.
2. **It defines what state it tracks and where.** Whatever bookkeeping your algorithm needs (which strategies you've tried, error patterns you've noticed, hypotheses to test, etc.) must live in committed files, not in your context window. Your context will be discarded between runs — your workspace persists.
3. **It uses feedback from `submit-train` to modify the workspace.** This is the actual learning step. If a training round leaves the workspace unchanged, no learning happened.
4. **It periodically validates progress** via `submit-val`, and uses the result *only* to decide whether to continue, revise, or roll back — not to memorize specific validation items (the framework only returns aggregate scores, so you can't anyway).
5. **The `answer` script reflects what you've learned.** What you put in workspace files only matters if `answer` actually consults them when called. See "Designing your `answer` script" below for patterns.

## CLI commands

All commands print JSON to stdout. Errors are JSON on stderr with non-zero exit codes.

- `agentkit task-info` — print the task description, your answer-format contract, the recorded `task_path`, and a state summary (consumed/skipped/pending counts, val checkpoint count).
- `agentkit next-train` — draw the next training sample. Returns `{id, prompt}`. Errors if a sample is already pending.
- `agentkit submit-train` — invoke `./answer` on the pending training sample, score it, return `{id, answer, reward, breakdown, gold_answer, notes}`. Marks the sample as consumed.
- `agentkit skip-train` — skip the pending training sample without seeing the gold. The sample is still consumed (you don't get to redraw it). Use this if you decide a sample isn't useful to learn from. Skip rate is tracked.
- `agentkit val-sample --n N` — return N validation samples (deterministic; same N always returns the same samples). Doesn't change state.
- `agentkit submit-val --n N` — invoke `./answer` on N validation samples, score them, and append an aggregate checkpoint to your val history. Subject to the validation gate below.

## Validation gating

`submit-val` is gated by git state:

1. **The workspace must have no uncommitted changes.** Validation is meant to measure a *committed* state of the workspace, so each val checkpoint corresponds to a real, reproducible artifact.
2. **The current HEAD sha must differ from the previous val checkpoint's sha.** Running validation on an unchanged workspace would just measure sampling noise. If you want a new val number, commit some change first.

The val history (in `.agentkit/state.json`) records the sha for each checkpoint, so the progress curve is auditable from the git history alone.

## What you cannot see

You only see gold answers for **training** samples. For validation, only the aggregate score is returned — no per-example feedback, no gold answers, nothing that would let you memorize or A/B test against specific val items. This is on purpose: val is for measuring, not for learning.

## Designing your `answer` script

Your `answer` script is the function `prompt → answer` that gets exercised at submit time. It is the deployed artifact. There are several patterns:

**Pattern 1: One-line wrapper around `claude -p` in this dir.**
```bash
#!/bin/bash
claude -p "$(cat)"
```
Simple but **has a role-collision problem**: the inner claude reads this dir's `CLAUDE.md`, sees "you are a learning agent", and gets confused. To use this pattern, you'd need to rewrite `CLAUDE.md` to be the answer agent's identity (and remove the learning-agent instructions). Workable but couples the two roles.

**Pattern 2: Sub-subdir with its own context.**
```
this_dir/
  answerer/
    CLAUDE.md       # the answer agent's identity, accumulated skills, knowledge
    skills/
    notes/
  answer            # script that does: cd answerer && claude -p "$(cat)"
```
Cleaner separation. The learning agent (you, in `this_dir/`) edits files in `answerer/` as part of learning. The answer agent's `cd answerer && claude -p` picks up `answerer/CLAUDE.md` automatically and never sees the learning-agent stuff. **This is the recommended pattern.**

**Pattern 3: Headless `claude -p --bare` with explicit context.**
```bash
#!/bin/bash
claude -p "$(cat)" --append-system-prompt "$(cat ANSWER_CONTEXT.md)" --bare
```
`--bare` skips CLAUDE.md, skills, etc. You pass the answer-agent identity via `--append-system-prompt`. Most explicit, no role collision, but loses the auto-discovery of skills/notes inside the workspace.

**Pattern 4: Direct API calls.**
```python
#!/usr/bin/env python3
import sys
from anthropic import Anthropic
prompt = sys.stdin.read()
system = open("ANSWER_CONTEXT.md").read()
resp = Anthropic().messages.create(
    model="claude-opus-4-6", max_tokens=4096,
    system=system,
    messages=[{"role": "user", "content": prompt}],
)
print(resp.content[0].text)
```
Maximum control over the inference call. Useful if you want to use different models, structured output, etc.

**Important constraint:** in any pattern, the answer process **must not read the task source** (which lives at `task_path`) and **must not query the underlying dataset**. The framework only feeds you prompts via stdin; produce answers from those alone (plus whatever you've learned and written into this workspace).

## Your first move

1. Run `agentkit task-info` to see the task and the answer format.
2. Decide on (or seed) a learning algorithm. Write it down in a file you commit. It doesn't need to be sophisticated — even "look at one training sample, reflect, edit `answer`, repeat" is a starting point. You can refine the algorithm itself as you learn.
3. Decide on an answer-script pattern (see above). Pattern 2 (sub-subdir) is recommended unless you have a reason to pick another.
4. Create a minimal `answer` script. Make it executable (`chmod +x answer`). It can be bad — the point is to have something measurable.
5. Commit the initial state.
6. Optionally run a small `submit-val --n 5` to establish a baseline. This requires your initial commit.
7. Start the loop: `next-train` → look at prompt → produce an answer → `submit-train` → reflect on feedback → modify the workspace → commit → repeat.
8. Periodically validate.

You are not in a hurry. The point of this experiment is *to think hard about each sample and make each one count*, not to power through. If a single training sample takes a lot of effort and produces a substantial workspace edit, that's a feature.

When to stop is up to your learning algorithm. Stopping cleanly means: commit any pending changes, run a final validation, summarize.

Good luck.
