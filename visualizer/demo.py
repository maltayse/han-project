"""Synthetic public demo. No filesystem, process inspection, or Claude requests."""
import time


class DemoCollector:
    def snapshot(self):
        now = time.time()
        stamp = '2026-01-01T12:00:00Z'
        sessions = [
            dict(id='demo-docs',name='DEMO · 문서 사이트 만들기',cwd='/demo/docs-site',pid=0,status='busy'),
            dict(id='demo-api',name='DEMO · API 테스트 팀',cwd='/demo/api',pid=0,status='idle'),
            dict(id='demo-design',name='DEMO · 디자인 실험실',cwd='/demo/design',pid=0,status='idle'),
        ]
        def node(id, session, parent, name, model, effort, status, activity, kind='agent'):
            observed = lambda value: dict(value=value,source='synthetic demo',at=stamp)
            return dict(id=id,sessionId=session,parentId=parent,name=name,kind=kind,status=status,
                        model=observed('claude-'+model+'-demo'),responseModel=observed('claude-'+model+'-demo'),
                        effort=observed(effort),requestedModel=model if kind=='agent' else None,
                        requestedEffort=effort if kind=='agent' else None,agentType='han-'+('builder' if model=='sonnet' else 'reviewer'),
                        task=name,activity=activity,lastAt=stamp,ended=status=='completed',
                        events=[dict(at=stamp,text=activity,kind='tool')])
        nodes = [node(s['id'],s['id'],None,s['name'],'opus','medium',s['status'],'작업을 나누고 결과를 통합합니다.','session') for s in sessions]
        roles = [
            ('scout','haiku','low','폴더 구조 살펴보기','Read · 프로젝트 구조를 정리했어요.','completed'),
            ('builder','sonnet','medium','첫 화면 만들기','Edit · 헤더와 탐색 메뉴 작업','observed'),
            ('reviewer','opus','high','접근성 검토','Read · 키보드 탐색과 대비 검토','observed'),
            ('tests','sonnet','medium','테스트 보강','Bash · 테스트 결과를 확인했어요.','completed'),
            ('docs','sonnet','medium','시작 안내 쓰기','Edit · 설치 방법 정리','completed'),
            ('deep','opus','high','상태 동기화 분석','Read · 이벤트 순서 분석','completed'),
            ('guide','haiku','low','관련 파일 찾기','Grep · 파일 위치를 정리했어요.','completed'),
            ('polish','sonnet','medium','모바일 화면 다듬기','Edit · 작은 화면 여백 조정','completed'),
        ]
        for key,model,effort,name,activity,status in roles:
            nodes.append(node('demo-'+key,'demo-docs','demo-docs',name,model,effort,status,activity))
        return dict(generatedAt=now,sessions=sessions,nodes=nodes,errors=[],root='synthetic-demo',version='1.0.0-demo')
