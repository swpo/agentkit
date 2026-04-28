# agentkit

A framework for agents that learn how to learn.

The premise: instead of training a model's weights to encode task strategies, give a frozen model a workspace it owns and a small set of data-access functions, and ask it to design and implement its own *learning algorithm* — a process that ingests training samples, reflects on feedback, modifies its own workspace, and periodically validates progress.

The artifact of training is the workspace itself: a git repo of skills, notes, code, scripts, and whatever else the agent invents to help it answer the task. Different harnesses (Claude Code, others) can drive the agent; the framework only provides the data and the rules.

## Status

Pre-alpha. v1 ships one task (`gene_perturbation_forward`) and a 6-command CLI.
