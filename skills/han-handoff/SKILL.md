---
name: han-handoff
description: Produce an evidence-based handoff for a successor without duplicating running work.
argument-hint: "[output path or leave blank]"
---
Use only for a checkpoint of an already user-authorized active task or a direct user request. Do not start new work. Create a handoff at $ARGUMENTS if an authorized path is supplied; otherwise output it for copying. Include:
- Objective, constraints, acceptance criteria and source of user authorization.
- Repo/worktree/branch/base and current HEAD; uncommitted changes and ownership.
- Decisions and reasons; completed and pending steps.
- Worker handles, status, requested/effective models and efforts, evidence/report locations.
- Exact test commands and observed results; never-run checks and risks.
- Uncertain operations and running jobs that must be checked, not repeated.
- Next 3 actions and stop conditions.
Exclude secrets. Distinguish facts from hypotheses. A successor must re-read Git/current files and actual worker state before resuming. Writing this document does not create or transfer a live session.
