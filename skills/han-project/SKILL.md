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

## Durable workflow (installed runtime)
The installer places the deterministic CLI at `${CLAUDE_SKILL_DIR}/../../han-project-runtime/han.py`. Use this skill directory, not the working repository, to resolve it. No model calls, messages or permissions are created by that CLI. Pass `--session ${CLAUDE_SESSION_ID}` with the actual current session ID. If unavailable, ask for or inspect actual runtime identity; never invent one for live work. Default private state is outside the repository at `~/.claude/han-project/`.

1. Start: `python3 <runtime>/han.py --session <session-id> start --repo <repo-root> --title <task>`; keep returned taskId.
2. Spawn a bounded native Agent with explicit role/model/effort, disjoint file ownership, dependencies, acceptance checks and return contract. Immediately register the returned native agent ID: `... register <task-id> --agent <native-id> --role han-builder --model sonnet --effort medium`. Registering is bookkeeping, not proof of spawning. At most three running workers; do not dispatch while a transfer is pending.
3. After the worker actually ends, the coordinator records `... result <attempt-id> --outcome ready|blocked|failed --summary <summary> --evidence <verification-log>`. Evidence must exist within repo or private state. Save new evidence under private state before recording; do not modify it afterwards. Never mark an active/unknown worker ended to bypass an interlock.
4. Independent review returns findings and its actual native ID. The coordinator records `... review <attempt-id> --reviewer <different-native-id> --verdict pass|changes_requested --evidence <review-log>`. Reading a log is not proof tests ran; examine actual command results. `... accept <attempt-id>` requires ready, stable evidence, same worktree and passing independent review. A failed/blocked result cannot be accepted.
5. A resumed/fixed worker receives a new attempt ID under the same task. Do not drop failed checks from history.
6. Same-session checkpoint: `... checkpoint <task-id> --next <action>`. Continue existing agents with native resume; a checkpoint does not change owner.
7. Cross-session handover: invoke `/han-handoff <task-id>`; successor uses `/han-resume <handoff-id>`. Stop new dispatches until the transfer is committed or cancelled. Prepared/received do not mean transferred. The source coordinator must confirm commit after the successor receipt; if source exited, resume that source session to confirm or diagnose explicitly—never silently steal its work.

Runtime records are coordinator attestations backed by file hashes and ownership versions, not a sandbox or authentication system. They cannot prevent another process from editing files or bypassing the workflow. Commands never grant user approval. Block on changed Git/evidence, running/unknown workers, duplicate receipt or stale ownership. Preserve private logs outside Git.
