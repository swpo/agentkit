# Agentkit task project

This directory is an **agentkit task project**. A task defines the *rules of the game* for an agentkit training run: what data the learning agent sees, what counts as a correct answer, how reward is computed.

## What you (the coding assistant) should do here

You are helping the user **author the task code** in this directory. You are *not* a learning agent — there is no training loop in this dir, no answer script, no `.agentkit/state.json`. Those things live in a separate *training run* directory the user will create later with `agentkit init-run --task <path-to-this-dir>`.

The task you are helping write must:

1. Implement the **agentkit Task protocol**. The protocol is documented in agentkit's `docs/AUTHORING_TASKS.md`. Read it before writing code. The protocol requires methods like `num_training_samples`, `get_training_sample`, `score_training`, `score_validation`, etc.
2. Live in **`task.py`** at the root of this dir, exporting a callable `get_task()` that returns the Task instance. (Same convention as prime's `load_environment()`.)
3. Use **disjoint training and validation pools**. Agents must never see val gold answers; the framework enforces this by only returning aggregate val scores, but the task's data layer is responsible for keeping the pools separate.
4. Use **stable, content-derived sample ids** so the framework can track which samples a learning agent has consumed across runs.
5. Cache expensive setup (dataset loading) using `functools.cached_property` or similar — the framework imports the task on every CLI invocation, so the per-call cost should be a cache hit.

See `README.md` in this dir for the user-facing description of the task and `task.py` for the stub to fill in. Edit both as you go.

## What you should NOT do here

- Do not run a training loop. Training happens in a separate directory created by `agentkit init-run --task <this dir>`. If the user asks to "start training", remind them that they need to `agentkit init-run` first in a new empty dir.
- Do not create `.agentkit/state.json`, `BOOTSTRAP.md`, `answer`, or any other training-run artifacts here. They belong in the run dir.
- Do not import or invoke `agentkit` framework internals from `task.py` beyond the public protocol types in `agentkit.task` (Sample, Task, TrainScoreResult, ValAggregateResult). The task should be a clean implementation of the protocol; the framework is the consumer.

## Typical authoring workflow

1. Read `docs/AUTHORING_TASKS.md` from the agentkit package (or ask the user to point you at it).
2. Read the existing `task.py` stub and `README.md` to see the placeholders.
3. Decide on the data source (HuggingFace dataset, local files, API, etc.).
4. Write the data loading + parsing in `task.py` (use `functools.cached_property` for the pools).
5. Write a stable sample id derivation (e.g. SHA1 of prompt content).
6. Write the scoring function — it should produce a reward in [0,1] and helpful `notes` for training feedback.
7. Edit `README.md` to describe the task: what's the question, where's the data, what's the answer format, what are the scoring rules, any domain notes the learning agent should know.
8. Test by running `python -c "from task import get_task; t = get_task(); print(t.num_training_samples()); print(t.get_training_sample(0))"` and similar.
9. Commit. Tell the user the task is ready and they can `mkdir <new-dir> && cd <new-dir> && agentkit init-run --task <this dir>` to start a training run.
