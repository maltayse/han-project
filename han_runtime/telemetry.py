"""Read-only join of observed native telemetry and explicitly recorded workflow events."""
import json


class WorkflowCollector:
    def __init__(self, native, store):
        self.native, self.store = native, store

    def snapshot(self):
        data=self.native.snapshot()
        try:
            workflow=self.store.overview()
        except Exception as e:
            data['errors'].append('Workflow state unavailable: '+type(e).__name__)
            workflow=dict(tasks=[],attempts=[],handoffs=[],events=[])
        data['tasks']=workflow['tasks']
        data['handoffs']=[dict(id=h['id'],taskId=h['task'],kind=h['kind'],source=h['source'],target=h['target'],
                               phase=h['phase'],version=h['version'],created=h['created'],
                               title=h['payload']['title'],nextSteps=h['payload']['nextSteps']) for h in workflow['handoffs']]
        data['workflowEvents']=workflow['events'][-100:]
        node_by_id={n['id']:n for n in data['nodes']}
        session_ids={s['id'] for s in data['sessions']}
        task_by_id={t['id']:t for t in workflow['tasks']}
        owners={t['owner']:t for t in workflow['tasks']}
        for h in workflow['handoffs']:
            owners.setdefault(h['source'],task_by_id[h['task']])
            if h['target']:
                owners.setdefault(h['target'],task_by_id[h['task']])
        for a in workflow['attempts']:
            owners.setdefault(a['coordinator'],task_by_id[a['task']])
        for sid,t in owners.items():
            if sid in session_ids:
                continue
            # Historical metadata never creates a fake live session or observed model.
            data['sessions'].append(dict(id=sid,name='담당 기록 · '+sid[:8],cwd=t['repo'],pid=None,status='recorded',historical=True))
            node=dict(id=sid,sessionId=sid,parentId=None,kind='session',name='담당 기록 · '+sid[:8],
                      status='recorded',historical=True,agentType='coordinator',model=None,responseModel=None,effort=None,
                      requestedModel=None,requestedEffort=None,task=t['title'],activity='로컬 작업/인계 기록 · 실행 여부 미확인',events=[])
            data['nodes'].append(node);node_by_id[sid]=node
        inbox=[]
        for a in workflow['attempts']:
            native_id=a['coordinator']+':'+a['agent']
            n=node_by_id.get(native_id)
            if n is not None:
                n['taskId']=a['task'];n['attemptId']=a['id'];n['outcome']=a['outcome']
                n['agentType']=a['role']
                n['resultSource']='coordinator attestation'
            if a['run']=='ended':
                inbox.append(dict(id=a['id'],taskId=a['task'],sessionId=a['coordinator'],agentId=a['agent'],
                                  agentType=a['role'],outcome=a['outcome'],summary=a['summary'],
                                  evidence=json.loads(a['evidence']),source='coordinator attestation'))
        data['inbox']=inbox
        return data
