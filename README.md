# agentkit

A framework for **agents that learn how to learn**.

The premise: instead of training a model's weights to encode task strategies, give a frozen model a workspace it owns and a small set of data-access functions, and ask it to design and implement its own *learning algorithm* — a process that ingests training samples, reflects on feedback, modifies its own workspace, and periodically validates progress.

The artifact of training is the workspace itself: a git repo of skills, notes, code, scripts, and whatever else the agent invents. Different harnesses (Claude Code, others) can drive the agent; the framework only provides the data and the rules.

## Layout

agentkit splits cleanly across three directories. Only this one — the framework — is shared across tasks and runs.

```
~/                              # or wherever you keep these
  agent/                        # this repo — the agentkit Python package + CLI
  agentkit-tasks/
    <task-name>/                # one git repo per task: data + scoring rules
  agentkit-runs/
    <run-name>/                 # one git repo per run: the learning agent's workspace
```

**`agent/` (this repo)** — the framework. Defines the `Task` protocol, owns the training-state schema, gates validation on git state, and exposes a CLI. Installed once via `uv tool install agentkit`. Users don't edit it.

**`agentkit-tasks/<name>/`** — a *task project*. Contains `task.py` implementing the `Task` protocol (data loading, prompts, scoring) and a `README.md` describing the task. Created with `agentkit init-task`. The learning agent never reads files in here — only the framework does, when loading the task in-process.

**`agentkit-runs/<name>/`** — a *training run*. The learning agent's workspace: `BOOTSTRAP.md`, `CLAUDE.md`, an executable `answer` script, accumulated skills/notes, and `.agentkit/state.json` (framework-owned). Created with `agentkit init-run --task <path-to-task-project>`, which records the absolute path to the task project so the CLI can load it on the agent's behalf.

Tasks and runs are independent git repos pushed to their own remotes. The agent only ever sees prompts and feedback through the CLI — never the task source.

## CLI

Setup (run once, anywhere):

- `agentkit install-skill` — install the global Claude Code skill at `~/.claude/skills/agentkit/`.
- `agentkit init-task` — scaffold a task project in the current (empty) directory.
- `agentkit init-run --task PATH` — scaffold a training run, recording PATH as the task source.

Training loop (run from inside a training run):

- `agentkit task-info` — task description, answer format, current state summary.
- `agentkit next-train` — draw the next training sample.
- `agentkit submit-train` — invoke `./answer` on the pending sample, score it, return reward + gold.
- `agentkit skip-train` — skip the pending sample (still consumes it).
- `agentkit val-sample --n N` — return N validation samples (no scoring).
- `agentkit submit-val --n N` — score N validation samples and append a checkpoint to history. Gated by a clean git tree *and* a new HEAD sha, so validation only runs when the workspace has actually changed.

All commands print JSON to stdout. Errors are JSON on stderr with non-zero exit.

## Install

```bash
uv tool install agentkit
agentkit install-skill        # makes the bundled Claude Code skill discoverable
```

## Quick start

```bash
# 1. author a task
mkdir -p ~/agentkit-tasks/my-task && cd ~/agentkit-tasks/my-task
agentkit init-task
# Open Claude Code here. The task-author CLAUDE.md auto-loads — fill in
# task.py per docs/AUTHORING_TASKS.md, edit README.md, commit.

# 2. start a training run
mkdir -p ~/agentkit-runs/my-run-001 && cd ~/agentkit-runs/my-run-001
agentkit init-run --task ~/agentkit-tasks/my-task
# Open Claude Code here. The learning-agent CLAUDE.md auto-loads. Read
# BOOTSTRAP.md, design a learning algorithm, then run the loop.
```

## See also

- [`agentkit/docs/AUTHORING_TASKS.md`](agentkit/docs/AUTHORING_TASKS.md) — the `Task` protocol in detail; read this when writing a task.
- [`agentkit/templates/training_run/BOOTSTRAP.md`](agentkit/templates/training_run/BOOTSTRAP.md) — the canonical spec of the learning agent's job; read this when running a training loop.
- [`agentkit/templates/global_skill/SKILL.md`](agentkit/templates/global_skill/SKILL.md) — what the bundled Claude Code skill tells the assistant when a user asks for help with agentkit.
- [swpo/agentkit-gpf-pilot](https://github.com/swpo/agentkit-gpf-pilot) — example training run.

## Status

Pre-alpha. The framework is small and intentionally rigid — the interesting design space is in the *learning algorithm* the agent invents inside its training run. Everything is subject to change.
