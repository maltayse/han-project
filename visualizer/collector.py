"""Read-only Claude Code telemetry. Never reads credentials or executes transcript tools."""
import json
import os
import re
import subprocess
import time
from collections import deque
from pathlib import Path


def short(value, limit=600):
    return str(value or '')[:limit]


def process_starts():
    # Claude's procStart registry uses UTC, independent of the terminal timezone.
    result = subprocess.run(['ps', '-axo', 'pid=,lstart='], capture_output=True, text=True, timeout=5, check=True,
                            env={**os.environ, 'TZ':'UTC', 'LC_ALL':'C'})
    return {int(bits[0]): ' '.join(bits[1:]) for line in result.stdout.splitlines() if len(bits := line.split()) >= 6}


class Transcript:
    def __init__(self, path):
        self.path = path
        self.reset()

    def reset(self):
        self.offset = 0
        self.identity = None
        self.mtime = None
        self.calls = {}
        self.events = deque(maxlen=12)
        self.bad_lines = 0
        self.data = dict(model=None, effort=None, responseModel=None, task='', activity='', lastAt=None, ended=False)

    def observed(self, value, source, stamp):
        return dict(value=short(value, 120), source=source, at=stamp) if value is not None else None

    def consume(self, r):
        kind, stamp = r.get('type'), r.get('timestamp')
        if stamp:
            self.data['lastAt'] = stamp
        if kind == 'api-request':
            params = r.get('params') or {}
            self.data['model'] = self.observed(params.get('model'), 'API request', stamp)
            self.data['effort'] = self.observed((params.get('output_config') or {}).get('effort'), 'API request', stamp)
            self.data['ended'] = False
        if kind == 'last-prompt' and r.get('lastPrompt'):
            self.data['task'] = short(r['lastPrompt'])
        if kind not in ('user', 'assistant'):
            return
        msg = r.get('message') or {}
        if kind == 'assistant':
            if msg.get('model') and msg['model'] != '<synthetic>':
                self.data['responseModel'] = self.observed(msg['model'], 'assistant response', stamp)
            # Explicit per-response effort is observed independently of settings/defaults.
            effort = r.get('perTurnEffort') or r.get('effort')
            if isinstance(effort, dict):
                effort = effort.get('level')
            if isinstance(effort, str):
                self.data['effort'] = self.observed(effort, 'assistant record', stamp)
            self.data['ended'] = msg.get('stop_reason') in ('end_turn', 'stop_sequence')
        content = msg.get('content') or []
        if isinstance(content, str):
            content = [dict(type='text', text=content)]
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_use':
                name = short(block.get('name'), 100)
                inp = block.get('input') or {}
                if name in ('Agent', 'Task'):
                    self.calls[block.get('id')] = {k:short(inp.get(k)) for k in ('description','model','effort','subagent_type')}
                # Tool names + descriptive fields only; no shell commands/outputs or raw payloads.
                label = short(inp.get('description') or inp.get('file_path') or inp.get('pattern') or '', 200)
                self.data['activity'] = name + (': ' + label if label else '')
                self.events.append(dict(at=stamp, text=self.data['activity'], kind='tool'))
            elif block.get('type') == 'text':
                value = short(block.get('text'))
                if kind == 'user' and value and not value.startswith(('<', '[Request interrupted')):
                    self.data['task'] = value
                    self.data['ended'] = False
                elif kind == 'assistant' and value:
                    self.data['activity'] = value
                    self.events.append(dict(at=stamp, text=value, kind='message'))

    def update(self):
        stat = self.path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if self.identity != identity or stat.st_size < self.offset or (stat.st_size == self.offset and self.mtime != stat.st_mtime_ns):
            self.reset()
        self.identity, self.mtime = identity, stat.st_mtime_ns
        with self.path.open('rb') as f:
            f.seek(self.offset)
            for line in f:
                if not line.endswith(b'\n'):
                    break
                self.offset += len(line)
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        self.consume(row)
                except (ValueError, TypeError, AttributeError):
                    self.bad_lines += 1
        return self.data


class Collector:
    def __init__(self, root=None, processes=process_starts):
        self.root = Path(root or Path.home() / '.claude')
        self.processes = processes
        self.cache = {}

    def read(self, path, errors):
        t = self.cache.setdefault(path, Transcript(path))
        try:
            t.update()
            if t.bad_lines:
                errors.append(f'{path.name}: malformed rows {t.bad_lines}')
        except (OSError, ValueError) as e:
            errors.append(f'{path.name}: {type(e).__name__}')
        return t

    def snapshot(self):
        errors, sessions, nodes, used = [], [], [], set()
        try:
            procs = self.processes()
        except (OSError, subprocess.SubprocessError) as e:
            procs = None
            errors.append(f'Process inspection failed: {type(e).__name__}')
        for path in sorted((self.root / 'sessions').glob('*.json')):
            try:
                reg = json.loads(path.read_text())
                pid, sid = reg.get('pid'), reg.get('sessionId')
                if not sid or not isinstance(pid, int):
                    continue
                if procs is not None and (pid not in procs or (reg.get('procStart') and ' '.join(reg['procStart'].split()) != procs[pid])):
                    continue
                cwd = reg.get('cwd') or ''
                encoded = re.sub(r'[^a-zA-Z0-9]', '-', cwd)
                transcript = self.root / 'projects' / encoded / (sid + '.jsonl')
                if not transcript.exists():
                    transcript = next((self.root / 'projects').glob('*/' + sid + '.jsonl'), transcript)
                parent = self.read(transcript, errors) if transcript.exists() else Transcript(transcript)
                used.add(transcript)
                session = dict(id=sid, name=short(reg.get('name') or sid[:8], 160), cwd=cwd, pid=pid,
                               status=reg.get('status') if procs is not None else 'unknown',
                               statusAt=reg.get('statusUpdatedAt'), startedAt=reg.get('startedAt'))
                sessions.append(session)
                local = {sid: (parent, {})}
                agent_dir = transcript.parent / sid / 'subagents'
                agent_ids = {p.name.split('.')[0][6:] for p in agent_dir.glob('agent-*') if p.name.endswith(('.jsonl','.meta.json'))}
                for aid in sorted(agent_ids):
                    ap = agent_dir / ('agent-' + aid + '.jsonl')
                    meta = {}
                    mp = agent_dir / ('agent-' + aid + '.meta.json')
                    if mp.exists():
                        try:
                            meta = json.loads(mp.read_text())
                        except (ValueError, OSError):
                            errors.append(f'{mp.name}: unreadable metadata')
                    local[sid + ':' + aid] = (self.read(ap, errors) if ap.exists() else Transcript(ap), meta)
                    used.add(ap)
                call_parents = {call_id:(nid, inp) for nid,(t,_) in local.items() for call_id,inp in t.calls.items()}
                for nid, (t, meta) in local.items():
                    link = call_parents.get(meta.get('toolUseId'))
                    requested = link[1] if link else {}
                    main = nid == sid
                    status = session['status'] or 'unknown'
                    if not main:
                        status = 'ended' if meta.get('finished') else ('response-ended' if t.data['ended'] else 'unknown')
                        if not meta.get('finished') and not t.data['ended'] and t.data['lastAt']:
                            # A timestamp is evidence of activity, not proof the agent is still running.
                            status = 'observed'
                    nodes.append(dict(id=nid, sessionId=sid, parentId=None if main else (link[0] if link else None),
                                      kind='session' if main else 'agent', status=status,
                                      name=session['name'] if main else short(meta.get('description') or requested.get('description') or nid.split(':')[-1],160),
                                      agentType=meta.get('agentType') or requested.get('subagent_type'),
                                      requestedModel=meta.get('model') or requested.get('model') or None,
                                      requestedEffort=meta.get('effort') or requested.get('effort') or None,
                                      events=list(t.events), **t.data))
            except (OSError, ValueError, TypeError, AttributeError) as e:
                errors.append(f'{path.name}: {type(e).__name__}')
        self.cache = {k:v for k,v in self.cache.items() if k in used}
        return dict(generatedAt=time.time(), sessions=sessions, nodes=nodes, errors=errors,
                    root=str(self.root), version='1.0.0')
