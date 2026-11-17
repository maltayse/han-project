"""Transactional task ownership, evidence and handoff records (not a security sandbox)."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid

ROLES = {'han-scout': ('haiku', 'low'), 'han-builder': ('sonnet', 'medium'),
         'han-deep': ('opus', 'high'), 'han-reviewer': ('opus', 'high'),
         'han-advisor': ('fable', 'high')}


class Conflict(ValueError):
    pass


def token(prefix):
    return prefix + '-' + uuid.uuid4().hex[:16]


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                          check=True, timeout=20).stdout


def snapshot(repo):
    repo = Path(repo).resolve()
    top = Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip()).resolve()
    if top != repo:
        raise Conflict('Use the repository root, not a subdirectory')
    try:
        head = git(repo, 'rev-parse', '--verify', 'HEAD').decode().strip()
    except subprocess.CalledProcessError:
        head = 'UNBORN'
    status = git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignore-submodules=none')
    digest = hashlib.sha256(status)
    # Include actual dirty bytes, not just the file names reported by git status.
    entries = status.split(b'\0')
    paths = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) >= 4:
            paths.append(os.fsdecode(entry[3:]))
            if entry[:1] in (b'R', b'C') or entry[1:2] in (b'R', b'C'):
                i += 1
                if i < len(entries) and entries[i]:
                    paths.append(os.fsdecode(entries[i]))
        i += 1
    for name in sorted(set(paths)):
        p = repo / name
        digest.update(os.fsencode(name))
        if p.is_symlink():
            digest.update(b'LINK:' + os.fsencode(os.readlink(p)))
        elif p.is_file():
            with p.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    digest.update(block)
        else:
            if p.is_dir():
                raise Conflict('Dirty submodules/directories are unsupported; reconcile them before handoff')
            digest.update(b'MISSING_OR_DIRECTORY')
    digest.update(git(repo, 'diff', '--cached', '--binary'))
    return dict(head=head, worktreeHash=digest.hexdigest())


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory or Path.home()/'.claude/han-project').expanduser().resolve()
        self.path = self.directory/'workflow.sqlite3'

    def connect(self, write=False):
        if not write:
            if not self.path.exists():
                return None
            if self.path.is_symlink():
                raise Conflict('Refusing symlink database')
            c = sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True, timeout=10)
        else:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.path.is_symlink():
                raise Conflict('Refusing symlink database')
            c = sqlite3.connect(self.path, timeout=10)
            os.chmod(self.path, 0o600)
            c.executescript('''
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, repo TEXT NOT NULL,
                  title TEXT NOT NULL, owner TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, task TEXT NOT NULL REFERENCES tasks(id),
                  agent TEXT NOT NULL, coordinator TEXT NOT NULL, role TEXT NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL,
                  run TEXT NOT NULL, outcome TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
                  evidence TEXT NOT NULL DEFAULT '[]', tree TEXT, review TEXT);
                CREATE TABLE IF NOT EXISTS handoffs(id TEXT PRIMARY KEY, task TEXT NOT NULL REFERENCES tasks(id),
                  kind TEXT NOT NULL, source TEXT NOT NULL, target TEXT, version INTEGER NOT NULL,
                  phase TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_transfer ON handoffs(task)
                  WHERE kind='transfer' AND phase IN ('prepared','received');
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                  task TEXT NOT NULL REFERENCES tasks(id), kind TEXT NOT NULL, payload TEXT NOT NULL,
                  created REAL NOT NULL);
            ''')
        c.row_factory = sqlite3.Row
        return c

    @contextlib.contextmanager
    def transaction(self):
        c = self.connect(write=True)
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def event(self, c, task, kind, **payload):
        c.execute('INSERT INTO events(task,kind,payload,created) VALUES(?,?,?,?)',
                  (task, kind, json.dumps(payload, ensure_ascii=False), time.time()))

    def task(self, c, id, owner=None):
        row = c.execute('SELECT * FROM tasks WHERE id=?', (id,)).fetchone()
        if not row:
            raise Conflict('Unknown task')
        if owner is not None and row['owner'] != owner:
            raise Conflict('Only the current coordinator can perform this action')
        return row

    def evidence(self, repo, paths):
        records = []
        for name in paths:
            p = Path(name).expanduser()
            if not p.is_absolute():
                p = Path(repo)/p
            if p.is_symlink():
                raise Conflict('Evidence must not be a symlink')
            p = p.resolve()
            if not any(p.is_relative_to(root) for root in (Path(repo), self.directory)):
                raise Conflict('Evidence must be inside the repository or workflow state directory')
            if not p.is_file() or p.stat().st_size > 10 * 1024 * 1024:
                raise Conflict('Evidence is missing, not a file, or larger than 10 MiB')
            records.append(dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        return records

    def capture_evidence(self,repo,paths):
        records=self.evidence(repo,paths)
        directory=self.directory/'evidence'
        if directory.is_symlink() or not directory.resolve().is_relative_to(self.directory):
            raise Conflict('Unsafe evidence directory')
        directory.mkdir(exist_ok=True,mode=0o700)
        copies=[]
        for record in records:
            data=Path(record['path']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=record['sha256']:
                raise Conflict('Evidence changed during capture')
            path=directory/(token('proof')+'.txt')
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(data)
            copies.append(dict(path=str(path),sourcePath=record['path'],sha256=record['sha256']))
        return copies

    def verify_evidence(self, repo, records, source=True):
        for old in records:
            if self.evidence(repo, [old['path']])[0]['sha256'] != old['sha256']:
                raise Conflict('Evidence changed; run verification again')
            if source and old.get('sourcePath') and self.evidence(repo,[old['sourcePath']])[0]['sha256']!=old['sha256']:
                raise Conflict('Source evidence changed; return fresh validation in a new attempt')

    def start(self, repo, session, title):
        if not session or not title.strip():
            raise Conflict('Session ID and title are required')
        repo = str(Path(repo).resolve())
        if self.directory.is_relative_to(Path(repo)):
            raise Conflict('Private workflow state must be outside the source repository')
        snapshot(repo)
        id = token('task')
        with self.transaction() as c:
            c.execute('INSERT INTO tasks(id,repo,title,owner) VALUES(?,?,?,?)', (id,repo,title,session))
            self.event(c,id,'task_started', sessionId=session)
        return id

    def register(self, task, owner, agent, role, model=None, effort=None):
        if role not in ROLES or not agent:
            raise Conflict('A known role and native agent ID are required')
        default_model, default_effort = ROLES[role]
        model, effort = model or default_model, effort or default_effort
        if model not in ('haiku','sonnet','opus','fable') or effort not in ('low','medium','high','xhigh','max'):
            raise Conflict('Unsupported requested model or effort')
        id = token('attempt')
        with self.transaction() as c:
            self.task(c,task,owner)
            if c.execute("SELECT 1 FROM handoffs WHERE task=? AND kind='transfer' AND phase IN ('prepared','received')",(task,)).fetchone():
                raise Conflict('Transfer pending; do not start another worker')
            active=c.execute("SELECT * FROM attempts WHERE coordinator=? AND run IN ('running','unknown')",(owner,)).fetchall()
            if len(active)>=3 or any(a['agent']==agent for a in active):
                raise Conflict('At most 3 workers; an agent cannot have two active attempts')
            c.execute('INSERT INTO attempts(id,task,agent,coordinator,role,model,effort,run,outcome) VALUES(?,?,?,?,?,?,?,?,?)',
                      (id,task,agent,owner,role,model,effort,'running','pending'))
            self.event(c,task,'worker_registered',attemptId=id,agentId=agent,role=role)
        return id

    def result(self, attempt, owner, outcome, summary, evidence=()):
        if outcome not in ('ready','blocked','failed') or not summary.strip():
            raise Conflict('Return ready, blocked or failed with a summary; acceptance is separate')
        with self.transaction() as c:
            a=c.execute('SELECT * FROM attempts WHERE id=?',(attempt,)).fetchone()
            if not a:
                raise Conflict('Unknown attempt')
            task=self.task(c,a['task'],owner)
            if a['run']!='running':
                raise Conflict('Attempt already ended; register a new attempt for a resumed run')
            records=self.capture_evidence(task['repo'],evidence)
            tree=snapshot(task['repo'])
            c.execute('UPDATE attempts SET run=?,outcome=?,summary=?,evidence=?,tree=? WHERE id=?',
                      ('ended',outcome,summary,json.dumps(records),json.dumps(tree),attempt))
            self.event(c,a['task'],'result_returned',attemptId=attempt,agentId=a['agent'],outcome=outcome)

    def review(self, attempt, owner, reviewer, verdict, evidence):
        if verdict not in ('pass','changes_requested') or not reviewer:
            raise Conflict('Reviewer ID and pass/changes_requested verdict required')
        with self.transaction() as c:
            a=c.execute('SELECT * FROM attempts WHERE id=?',(attempt,)).fetchone()
            if not a:
                raise Conflict('Unknown attempt')
            task=self.task(c,a['task'],owner)
            if a['agent']==reviewer or a['outcome']!='ready':
                raise Conflict('Only ready results may receive independent review; no self review')
            if snapshot(task['repo'])!=json.loads(a['tree']):
                raise Conflict('Worktree changed since the result; return fresh evidence in a new attempt')
            records=self.capture_evidence(task['repo'],evidence)
            if not records:
                raise Conflict('A review evidence file is required')
            self.verify_evidence(task['repo'],json.loads(a['evidence']))
            review=dict(reviewerId=reviewer,verdict=verdict,evidence=records,source='coordinator attestation')
            c.execute('UPDATE attempts SET review=?,outcome=? WHERE id=?',
                      (json.dumps(review),'ready' if verdict=='pass' else 'changes_requested',attempt))
            self.event(c,a['task'],'review_recorded',attemptId=attempt,verdict=verdict)

    def accept(self, attempt, owner):
        with self.transaction() as c:
            a=c.execute('SELECT * FROM attempts WHERE id=?',(attempt,)).fetchone()
            if not a:
                raise Conflict('Unknown attempt')
            task=self.task(c,a['task'],owner)
            review=json.loads(a['review'] or '{}')
            if a['outcome']!='ready' or review.get('verdict')!='pass' or not json.loads(a['evidence']):
                raise Conflict('Acceptance requires a ready result, test/validation evidence and independent passing review')
            if snapshot(task['repo'])!=json.loads(a['tree']):
                raise Conflict('Worktree changed since verification')
            self.verify_evidence(task['repo'],json.loads(a['evidence'])+review['evidence'])
            c.execute("UPDATE attempts SET outcome='accepted' WHERE id=?",(attempt,))
            self.event(c,a['task'],'result_accepted',attemptId=attempt)

    def prepare(self, task, owner, next_steps, kind='transfer', context=()):
        if kind not in ('transfer','checkpoint') or not 1<=len(next_steps)<=3 or not all(s.strip() for s in next_steps):
            raise Conflict('Specify checkpoint/transfer and one to three concrete next steps')
        id=token('handoff')
        with self.transaction() as c:
            t=self.task(c,task,owner)
            if kind=='transfer' and c.execute("SELECT 1 FROM handoffs WHERE task=? AND kind='transfer' AND phase IN ('prepared','received')",(task,)).fetchone():
                raise Conflict('Transfer already pending; cancel it before preparing another')
            attempts=[dict(a) for a in c.execute('SELECT * FROM attempts WHERE task=?',(task,))]
            evidence=[]
            for a in attempts:
                evidence+=json.loads(a['evidence'])
                evidence+=json.loads(a['review'] or '{}').get('evidence',[])
            self.verify_evidence(t['repo'],evidence,source=False)
            notes=self.capture_evidence(t['repo'],context)
            evidence+=notes
            payload=dict(schemaVersion=1,snapshot=snapshot(t['repo']),nextSteps=next_steps,
                         evidence=evidence,context=notes,attempts=attempts,title=t['title'],repo=t['repo'])
            c.execute('INSERT INTO handoffs VALUES(?,?,?,?,?,?,?,?,?)',
                      (id,task,kind,owner,None,t['version'],'checkpoint' if kind=='checkpoint' else 'prepared',json.dumps(payload),time.time()))
            self.event(c,task,'checkpoint' if kind=='checkpoint' else 'handoff_prepared',handoffId=id)
            directory=self.directory/'handoffs'
            if directory.is_symlink() or not directory.resolve().is_relative_to(self.directory):
                raise Conflict('Unsafe handoff directory')
            directory.mkdir(exist_ok=True,mode=0o700)
            path=directory/(id+'.md')
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:
                f.write(self.render_document(id,dict(kind=kind,source=owner,target=None,phase='checkpoint' if kind=='checkpoint' else 'prepared'),payload))
        return id

    def checked_handoff(self,c,id):
        h=c.execute('SELECT * FROM handoffs WHERE id=?',(id,)).fetchone()
        if not h:
            raise Conflict('Unknown handoff')
        t=self.task(c,h['task'])
        if h['kind']!='transfer' or t['owner']!=h['source'] or t['version']!=h['version']:
            raise Conflict('Not a transferable checkpoint, or ownership version changed')
        payload=json.loads(h['payload'])
        if snapshot(t['repo'])!=payload['snapshot']:
            raise Conflict('HEAD, index or uncommitted contents changed; prepare a fresh handoff')
        self.verify_evidence(t['repo'],payload['evidence'],source=False)
        current=[dict(a) for a in c.execute('SELECT * FROM attempts WHERE task=? ORDER BY rowid',(t['id'],))]
        if current!=payload['attempts']:
            raise Conflict('Worker result/review states changed; cancel and prepare a fresh handoff')
        if c.execute("SELECT 1 FROM attempts WHERE task=? AND run IN ('running','unknown')",(t['id'],)).fetchone():
            raise Conflict('Existing worker is running or unverified; do not restart its work')
        return h,t

    def receive(self,id,target):
        if not target:
            raise Conflict('Successor session ID required')
        with self.transaction() as c:
            h,t=self.checked_handoff(c,id)
            if h['phase']!='prepared' or target==h['source']:
                raise Conflict('Already received or not a different successor session')
            c.execute("UPDATE handoffs SET phase='received',target=? WHERE id=?",(target,id))
            self.event(c,t['id'],'handoff_received',handoffId=id,sourceSessionId=h['source'],targetSessionId=target)

    def commit(self,id,source):
        with self.transaction() as c:
            h,t=self.checked_handoff(c,id)
            if h['phase']!='received' or h['source']!=source:
                raise Conflict('Only the source may confirm a received transfer')
            c.execute('UPDATE tasks SET owner=?,version=version+1 WHERE id=?',(h['target'],t['id']))
            c.execute("UPDATE handoffs SET phase='committed' WHERE id=?",(id,))
            self.event(c,t['id'],'handoff_committed',handoffId=id,sourceSessionId=source,targetSessionId=h['target'])

    def cancel(self,id,owner):
        with self.transaction() as c:
            h=c.execute('SELECT * FROM handoffs WHERE id=?',(id,)).fetchone()
            if not h:
                raise Conflict('Unknown handoff')
            self.task(c,h['task'],owner)
            if h['phase'] not in ('prepared','received'):
                raise Conflict('Only a pending transfer may be cancelled')
            c.execute("UPDATE handoffs SET phase='cancelled' WHERE id=?",(id,))
            self.event(c,h['task'],'handoff_cancelled',handoffId=id)

    def overview(self):
        c=self.connect()
        if c is None:
            return dict(tasks=[],attempts=[],handoffs=[],events=[])
        try:
            c.execute('BEGIN')
            result={name:[dict(row) for row in c.execute('SELECT * FROM '+name+' ORDER BY rowid')] for name in ('tasks','attempts','handoffs','events')}
            for h in result['handoffs']:
                h['payload']=json.loads(h['payload'])
            for e in result['events']:
                e['payload']=json.loads(e['payload'])
            return result
        finally:
            c.close()

    def document(self,id):
        data=self.overview()
        h=next((h for h in data['handoffs'] if h['id']==id),None)
        if not h:
            raise Conflict('Unknown handoff')
        return self.render_document(id,h,h['payload'])

    @staticmethod
    def render_document(id,h,p):
        return '\n'.join(['# '+p['title'], '', '인계 ID: '+id, '종류: '+h['kind'], '상태: '+h['phase'],
                          '기존 담당: '+h['source'], '후임: '+str(h['target'] or '미지정'),
                          '저장소: '+p['repo'], 'HEAD: '+p['snapshot']['head'], '',
                          '## 다음 행동', *['- '+s for s in p['nextSteps']], '',
                          '## 배경·결정·미실행 검증 근거', *['- '+e['path']+' (sha256 '+e['sha256']+')' for e in p.get('context',[])], '',
                          '## Worker 상태', *['- '+a['agent']+': '+a['run']+' / '+a['outcome']+' — '+a['summary'] for a in p['attempts']], '',
                          '문서 생성/수신은 담당 이전 확정 또는 사용자 승인이 아닙니다. 실제 상태와 권한을 다시 확인하세요.', ''])
