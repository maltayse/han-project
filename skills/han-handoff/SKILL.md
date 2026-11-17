---
name: han-handoff
description: Prepare a verified checkpoint or cross-session handover without changing ownership prematurely.
argument-hint: "[task-id] [checkpoint or transfer]"
disable-model-invocation: true
---
# 인계 준비

Task: $ARGUMENTS

Use only for the current authorized task. Do not start a new project, create a worker, change permissions or send messages to another person/session. No extra handoff agent is needed.

The installed CLI is `${CLAUDE_SKILL_DIR}/../../han-project-runtime/han.py`. Resolve it from this skill's actual installation directory. Pass `--session ${CLAUDE_SESSION_ID}` with the actual coordinator ID. State is private and outside Git by default. If this is a legacy task without a task ID, inspect Git/workers and start a tracking task under the actual current coordinator before preparing; clearly record any still-running/unknown workers, never omit them to permit transfer.

1. Re-read current repo/worktree/branch/HEAD, uncommitted changes, ownership, requested and observed model/effort, exact test outcomes, unresolved blockers and existing live jobs. Preserve user changes. Do not claim that all workers ended without evidence.
2. Keep a short checkpoint note in the private state directory containing objective/authorization, decisions, changed files, executed and unrun checks, evidence locations and stop conditions. Existing sensitive context stays local. Do not copy raw conversation or credentials into public source files.
3. Same-session compaction/phase boundary: `python3 <runtime>/han.py --session <actual-id> checkpoint <task-id> --next <action> --context <private-checkpoint-note>`. Keep ownership and use existing native agent IDs when resuming. This is not a session transfer.
4. Different successor: `... handoff <task-id> --next <action-1> --next <action-2> --next <action-3> --context <private-checkpoint-note>`. One to three concrete next steps are allowed. The CLI freezes Git/evidence and creates a local summary document, handoff ID and `/han-resume <id>` instruction. Stop dispatching while prepared. Running workers must finish and be reconciled before receipt; if they change the frozen snapshot, cancel and re-prepare.
5. Return the handoff ID, local document path, current phase and one copyable resume instruction. Prepared is not received or committed. Do not claim to have created or transferred a live session.
6. After successor receipt, the source runs `... commit <handoff-id>` to revalidate and finalize. No ownership change occurs until this succeeds. `... cancel <handoff-id>` releases a pending transfer without changing owner.

The runtime records workflow checks, not authorization or OS isolation. Do not infer a successor from a same-folder session. Do not repeat uncertain operations, approvals or active jobs. If the source session exited, resume it to reconcile and confirm; do not silently restart its work in another session.
