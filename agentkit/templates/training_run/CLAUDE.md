# Agentkit training run

This directory is an **agentkit training run**. You are the **learning agent**.

Your job is to iteratively improve this directory so that the `answer` script (an executable file you create and edit) gets better at the task. The task itself lives in a *separate* directory you cannot see — you only interact with it through the `agentkit` CLI.

## What you should do

1. **Read `BOOTSTRAP.md`** in this dir for the full framework contract, the CLI surface, the validation gating rules, and what counts as a valid learning algorithm.
2. **Run `agentkit task-info`** to see the task description, the answer format, and your current state.
3. **Design a learning algorithm**, write it down in a committed file, and run it. Start simple, refine as you learn.

## What you must NOT do

- **Do not look for or read the task source.** It does not live in this directory. It lives at an absolute path recorded in `.agentkit/state.json` (`task_path` field). You can see the path if you want — but you must not open the file at that path or anything inside it. The framework loads the task on your behalf and reaches up to wherever it is. If you read the task code or its data, you can extract gold answers and your validation history becomes meaningless. The git audit trail will catch you.
- **Do not modify `.agentkit/state.json`.** It is framework state. Mutate it only by calling `agentkit` CLI commands.
- **Do not invoke `agentkit init-task` or `agentkit init-run` from here.** Those are bootstrap commands for setting up new task projects and training runs.

## On running the training loop

When the user asks to start training (or when you've decided you understand the task and are ready), follow the procedure in `BOOTSTRAP.md`:

```
agentkit next-train         # draw a sample
# (think about it, write your answer or invoke ./answer)
agentkit submit-train       # score it and get feedback
# (reflect on the feedback, edit your workspace, commit)
agentkit val-sample --n N   # peek at validation samples (no scoring)
agentkit submit-val --n N   # score validation (gated by clean tree + new sha)
```

The user is your collaborator and may intervene at any time. Yield to them between training samples if they have feedback.
