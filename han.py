#!/usr/bin/env python3
"""Deterministic local task/handoff CLI; no model calls or session messages."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from han_runtime.store import Store, Conflict


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir',type=Path,help='Private state directory (default ~/.claude/han-project)')
    p.add_argument('--session',default=os.environ.get('CLAUDE_SESSION_ID'),help='Actual coordinator session ID; required for mutations')
    sub=p.add_subparsers(dest='command',required=True)
    start=sub.add_parser('start');start.add_argument('--repo',type=Path,default=Path.cwd());start.add_argument('--title',required=True)
    register=sub.add_parser('register');register.add_argument('task');register.add_argument('--agent',required=True);register.add_argument('--role',required=True);register.add_argument('--model');register.add_argument('--effort')
    result=sub.add_parser('result');result.add_argument('attempt');result.add_argument('--outcome',choices=['ready','blocked','failed'],required=True);result.add_argument('--summary',required=True);result.add_argument('--evidence',action='append',default=[])
    review=sub.add_parser('review');review.add_argument('attempt');review.add_argument('--reviewer',required=True);review.add_argument('--verdict',choices=['pass','changes_requested'],required=True);review.add_argument('--evidence',action='append',required=True)
    accept=sub.add_parser('accept');accept.add_argument('attempt')
    for command in ('checkpoint','handoff'):
        q=sub.add_parser(command);q.add_argument('task');q.add_argument('--next',dest='next_steps',action='append',required=True);q.add_argument('--context',action='append',default=[],help='Private note with objective, decisions, checks not run and stop conditions')
    for command in ('receive','commit','cancel','show'):
        sub.add_parser(command).add_argument('handoff')
    sub.add_parser('status')
    args=p.parse_args()
    store=Store(args.state_dir)
    try:
        if args.command not in ('status','show') and not args.session:
            raise Conflict('Pass --session with the actual coordinator session ID; never invent one for live work')
        c=args.command
        if c=='start':
            output=dict(taskId=store.start(args.repo,args.session,args.title))
        elif c=='register':
            output=dict(attemptId=store.register(args.task,args.session,args.agent,args.role,args.model,args.effort))
        elif c=='result':
            store.result(args.attempt,args.session,args.outcome,args.summary,args.evidence);output=dict(recorded=True)
        elif c=='review':
            store.review(args.attempt,args.session,args.reviewer,args.verdict,args.evidence);output=dict(recorded=True)
        elif c=='accept':
            store.accept(args.attempt,args.session);output=dict(accepted=True)
        elif c in ('handoff','checkpoint'):
            id=store.prepare(args.task,args.session,args.next_steps,'transfer' if c=='handoff' else 'checkpoint',args.context)
            # Markdown is a view of the durable database; never the ownership authority.
            path=store.directory/'handoffs'/(id+'.md')
            output=dict(handoffId=id,document=str(path),ownershipChanged=False,
                        resumePrompt='/han-resume '+id if c=='handoff' else '같은 세션과 기존 agent ID로 이어가세요.')
        elif c=='show':
            print(store.document(args.handoff));return
        elif c=='status':
            output=store.overview()
        else:
            getattr(store,c)(args.handoff,args.session);output=dict(recorded=True)
        print(json.dumps(output,ensure_ascii=False,indent=2))
    except (Conflict,OSError,subprocess.SubprocessError,ValueError) as e:
        p.exit(1,str(e)+'\n')


if __name__=='__main__':main()
