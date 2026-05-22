---
name: alab-experiment-worker
description: Use when operating inside an ALab experiment worktree with a worktree token to inspect status, edit candidate code, run evaluations, submit final results, and read visible experiment evidence without project admin or root privileges.
---

# ALab Experiment Worker

## Overview

Use this skill when Codex is working inside one ALab experiment worktree. The worker improves the candidate source, can inspect visible historical experiment evidence for ideas, runs ALab evaluation from the worktree token context, and submits the final result when a passed run supports the finished work.

This skill is not a project manager or global administrator. It must not use project admin keys, root keys, catalog commands, cache commands, project configuration mutation, or lifecycle removal commands.

## Operating Rules

- Trust only the current worktree context and its `.alab/token`.
- Do not read, print, copy, commit, or rewrite raw tokens or keys.
- Do not edit `.alab/`, ALab home records, hidden evaluator assets, or project control files.
- Edit only task-relevant source files inside the experiment worktree.
- Keep changes reviewable: prefer focused iterations, deterministic checks, and concise run messages.
- Use `alab help` before unfamiliar commands; commands outside the worktree token surface must be treated as unavailable.
- If ALab returns `COMMAND_UNAVAILABLE`, stop that branch and report the missing capability instead of trying to bypass it.

## Capabilities

This is a capability guide, not a required sequence. Use the capabilities that fit the task:

- Inspect current context with `alab status` and `alab help`.
- Read task files and project instructions that are present in the worktree.
- Inspect visible historical experiments with `alab observe experiments ...` and related visible runs, artifacts, logs, and annotations. Use this evidence to find promising approaches, avoid repeated failures, and understand prior best or final commits. Visibility is still enforced by ALab; do not try to access hidden or unavailable records.
- When a visible historical experiment looks relevant, create an inspection checkout with `alab exp checkout <exp_id> --path <dir> --commit best|final|latest`, read its source code, and compare it with the current worktree. Copy only task-relevant source files or snippets into the current experiment worktree when they are genuinely useful; never copy `.alab/`, raw tokens, hidden assets, or project control files.
- Change task-relevant source files in the worktree and keep the implementation understandable for later workers.
- Run local cheap checks when they exist, then run `alab run --message "<brief reason>"`.
- Diagnose failed or weak runs using visible stdout/stderr previews, warning codes, artifacts, logs, metrics, and annotations.
- When the intended changes are complete and the current worktree has a passed run supporting them, submit the result with a factual message, summary, feedback, and refs.

## Submit Guidance

- Submit only after a passed run for the current candidate, unless the user or controller explicitly asks for a non-passed closeout.
- Use `--ref none` only when the result does not depend on or intentionally reference prior experiments.
- If the work was inspired by, derived from, compared against, or intentionally continues visible historical experiments, pass each relevant experiment id as repeated `--ref <exp_id>`.
- Do not invent refs, cite inaccessible experiment ids, or cite a visible experiment only because it exists.
- Keep `--message` short. Put the substantive record in `--summary`/`--summary-file` and `--feedback`/`--feedback-file`: what changed, which passed run supports it, key metrics, which refs mattered, and remaining risks.
- If no submit is performed, clearly state the blocking reason and the best run evidence available.

## Command Reference

Read [references/commands.md](./references/commands.md) when you need the worker command surface, observe patterns, or examples for run and submit.
