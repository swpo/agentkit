---
name: agentkit
description: Help the user use agentkit — a framework where an agent learns to solve a task by iteratively building up a workspace of skills, notes, and code instead of by updating model weights. Use when the user wants to set up an agentkit task, start an agentkit training run, run the agentkit training loop, or asks how to use agentkit.
---

# Agentkit

Agentkit is a framework for **agents that learn how to learn**. Instead of training model weights, the agent iteratively improves a *workspace* — a directory of files (skills, notes, code, an `answer` script) — by consuming training samples, reflecting on feedback, and committing changes.

The framework provides:
- A task interface (the rules of the game)
- A CLI for getting samples, submitting answers, and validating progress
- Git-gated validation so the trained agent is an auditable git history

The user designs the *learning algorithm* (how reflection works, when to validate, what state to track). You are here to help.

## Two phases, two directories

Agentkit cleanly separates **task authoring** from **training**:

1. **A task project** (directory): contains `task.py` implementing the agentkit Task protocol, plus a README. This is where the *rules of the game* live: data loading, prompts, scoring. Created with `agentkit init-task`.
2. **A training run** (directory): contains the learning agent's workspace — `BOOTSTRAP.md`, `CLAUDE.md`, `.agentkit/state.json`, eventually an `answer` script and accumulated skills/notes. The training run *references* a task project at an absolute path (recorded in state). Created with `agentkit init-run --task <path-to-task-project>`.

These are two separate top-level directories. The task author works in one; the learning agent works in the other; they push to separate git remotes.

## The typical workflow

```
# 1. set up a task project
mkdir ~/agentkit-tasks/my-task && cd ~/agentkit-tasks/my-task
agentkit init-task
# claude code is now in this dir; help the user write task.py per
# AUTHORING_TASKS.md (in the agentkit package's docs/), edit README.md
git commit -am "task code"

# 2. set up a training run referencing the task
mkdir ~/agentkit-runs/my-run-001 && cd ~/agentkit-runs/my-run-001
agentkit init-run --task ~/agentkit-tasks/my-task
# claude code is now in this dir; the learning agent CLAUDE.md auto-loads
# and the user can say "start training" to begin the loop

# 3. share
cd ~/agentkit-tasks/my-task && git push          # task remote
cd ~/agentkit-runs/my-run-001 && git push        # trained agent remote
```

## What the user is probably asking you to do

**If they want to start fresh** (no task project, no training run yet):
- Ask them what task they want to solve. Help them pick a name.
- `mkdir ~/agentkit-tasks/<name> && cd ~/agentkit-tasks/<name>`.
- Run `agentkit init-task`. Read the resulting `CLAUDE.md` for guidance on writing the task.
- Help them write `task.py` per the protocol in agentkit's `docs/AUTHORING_TASKS.md`. Test it locally.
- When the task is solid, suggest creating a training run: `mkdir ~/agentkit-runs/<run-name> && cd ~/agentkit-runs/<run-name> && agentkit init-run --task ~/agentkit-tasks/<name>`.
- Then `cd` into the training run, open claude code (or stay in this session if cwd is already there), and the inner CLAUDE.md will guide the learning agent.

**If they have a task project but no training run yet**:
- `mkdir ~/agentkit-runs/<run-name> && cd ~/agentkit-runs/<run-name>`.
- `agentkit init-run --task <abs path to task project>`.
- Then start a fresh claude code session in the new dir.

**If they're already in a training run** (`.agentkit/state.json` exists):
- DO NOT proceed using this skill. The training run has its own `CLAUDE.md` and `BOOTSTRAP.md` that define the learning agent's identity and procedure. Read those instead. This skill is for orientation, not for running the training loop itself.

## CLI commands cheat sheet

Setup:
- `agentkit init-task` — scaffold a task project in cwd (must be empty)
- `agentkit init-run --task PATH` — scaffold a training run in cwd (must be empty), recording PATH as the task source

Training loop (run from inside a training run dir):
- `agentkit task-info` — show task, answer format, state summary
- `agentkit next-train` — draw the next training sample
- `agentkit submit-train` — score the pending sample, return feedback + gold
- `agentkit skip-train` — skip the pending sample without seeing gold
- `agentkit val-sample --n N` — fetch N validation samples (deterministic)
- `agentkit submit-val --n N` — score validation, append checkpoint (gated by clean tree + new git sha)

## What NOT to do

- Don't run training commands (`next-train`, `submit-train`, etc.) from this skill. Those belong to the learning agent in a training run dir.
- Don't write `task.py` for a workspace that's already a training run — task code lives in the task project, never in the training run.
- Don't tell the user to combine task and training in one dir. The separation is intentional and load-bearing.
