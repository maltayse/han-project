---
name: han-project
description: Complex multi-module project coordination with explicit adaptive model and effort routing.
argument-hint: "[task]"
disable-model-invocation: true
---
# Project mode
Task: $ARGUMENTS
Recommended parent Fable/medium (choose /model fable and /effort medium before invoking). Use high only for unusually ambiguous planning. This skill does not change the parent model.
1. Inspect repo, constraints, current changes and measurable acceptance criteria. Build a small dependency graph and allocate file ownership before execution. Use a cheap scout for bulk exploration; verify critical facts yourself.
2. Route each independent task via non-fork Agent with explicit model and effort:
   - han-scout: haiku/low for precise read-only search and log summaries.
   - han-builder: sonnet/medium for bounded routine implementation and tests.
   - han-deep: opus/high for multi-module debugging or complex changes.
   - han-reviewer: opus/high for independent correctness/security review.
   - han-advisor: fable/high only for unresolved high-impact architecture decisions; consult once.
3. Do not assign all workers the coordinator model. Reassess routing using actual test failures, scope expansion and ambiguity, not just task wording. Small tasks should stay serial.
4. Run at most 3 workers. Use worktree isolation where tool-supported and necessary. Record branch/worktree and base revision. If unsupported, split disjoint files or run serially; never invent Orca panes or peer messaging.
5. Persist an execution ledger under docs/agent-work/<task-id>/ when authorized: plan, owner/status, requested/effective model and effort, evidence paths, pending integration and next steps. Only the coordinator edits the central ledger; workers write separate reports.
6. Integrate sequentially, verify each diff, run aggregate tests and obtain independent review. Fix/retest before final report. Record completed and unverified stages separately.
7. At a major phase boundary or before context handover, invoke han-handoff through Skill for the already authorized task checkpoint, with an authorized output path. Verify running jobs before a successor restarts work.

## Guardrails
- Preserve user changes. Read project CLAUDE.md, test instructions and applicable skills. Keep the existing superpowers-first preference; these modes select routing, not a competing development process.
- Check the actual tools and model capabilities. Never claim an agent ran from a prompt alone. Record requested and effective model/effort when observable; otherwise mark effective values unverified.
- Never change credentials, permission mode, billing/extra usage, or security settings. No bypass-permissions. Stop on authorization/policy failures, do not model-hop around them.
- Max 3 concurrent workers; each has one task, owned files, forbidden files, dependencies, acceptance criteria and verification commands. Same-file edits are serial. Worktrees isolate files, not security.
- Model/effort must be explicit for every non-fork Agent call. Supported combinations only. No unbounded recursion or worker-created workers.
- For reasoning failure: inspect evidence, increase effort once if useful, then at most one model escalation. At 2 unsuccessful attempts on a task, stop and diagnose/replan rather than repeat. Infrastructure/auth failures are not reasoning failures.
- Cheap deterministic checks use lint/typecheck/tests, not an LLM. Security/auth/data-loss review is high-risk, never a low-effort quick check.
- Return concise findings with file/line evidence, actual commands/results, diff/commit when present, unresolved risks. Keep bulky evidence in task files, not the coordinator context. Do not claim tests passed unless executed.
- Before final completion, independently review changed code and run integrated tests. Do not push, merge or deploy unless requested.
- These are behavioral policies, not a hard budget or sandbox. Respect runtime limits and user approvals.

## Compact worker returns
At dispatch, give the worker its role-specific return contract and a soft final-response budget: scout ~300, builder ~500, deep/reviewer ~700, advisor ~500 tokens. These are approximate targets for the final handback only, not limits on reasoning, tool use or required verification. A task-specific budget may override them; preserve critical evidence even if the target must be exceeded.
The return is a decision packet: status (done/partial/blocked) and conclusion; changed files or findings; verification (actual commands/results, failed and never-run checks); risks/blockers and next action; evidence locators. Distinguish task implementation from verification status.
Keep bulk logs/diffs in an existing artifact or, for write-capable workers only, an authorized task-specific report path. Read-only roles cite existing file:line/log locations, or include a minimal relevant excerpt when no artifact exists; they do not create files or request broader tools just to compress output. A locator must actually exist and be readable by the coordinator; otherwise say unavailable and include the essential evidence inline.
Before integration, inspect the referenced changed code and critical failure/test evidence, not just the summary. If the return omits a required field or contradicts evidence, request the missing delta or inspect it directly rather than restarting the worker. Never hide failed/unrun checks, unresolved security/data-loss risks or uncertain operations to meet a budget. Request larger detail only where the decision needs it. This reduces main-context payload, not necessarily total tokens, latency or billing.
