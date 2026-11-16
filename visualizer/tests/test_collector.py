import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from collector import Transcript, Collector, process_starts


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, p, rows):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def test_partial_incremental_and_truncate(self):
        p = self.root / 'a.jsonl'
        p.write_text('{"type":"api-request","params":{"model":"opus",')
        t = Transcript(p)
        t.update()
        self.assertIsNone(t.data['model'])
        with p.open('a') as f:
            f.write('"output_config":{"effort":"high"}},"timestamp":"2026-01-01"}\n')
        t.update()
        self.assertEqual(t.data['effort']['value'], 'high')
        self.write(p, [{'type': 'api-request', 'params': {'model': 'haiku'}}])
        t.update()
        self.assertEqual(t.data['model']['value'], 'haiku')
        self.assertIsNone(t.data['effort'])

    def test_hierarchy_and_request_provenance(self):
        sid = 'session-1'
        self.write(self.root / 'sessions/123.json', [])
        (self.root / 'sessions/123.json').write_text(json.dumps({'pid':123,'sessionId':sid,'cwd':'/project','status':'busy','procStart':'start'}))
        base = self.root / 'projects/-project'
        self.write(base / (sid + '.jsonl'), [
            {'type':'api-request','timestamp':'2026-01-01','params':{'model':'opus','output_config':{'effort':'xhigh'}}},
            {'type':'assistant','message':{'model':'opus','content':[{'type':'tool_use','id':'tool-a','name':'Agent','input':{'description':'Build','model':'sonnet','effort':'high'}}]}}
        ])
        agents = base / sid / 'subagents'
        agents.mkdir(parents=True)
        (agents / 'agent-a.meta.json').write_text(json.dumps({'toolUseId':'tool-a','description':'Build','model':'sonnet','effort':'high'}))
        self.write(agents / 'agent-a.jsonl', [{'type':'assistant','message':{'model':'sonnet-real','content':[{'type':'tool_use','id':'tool-b','name':'Agent','input':{}}]}}])
        (agents / 'agent-b.meta.json').write_text(json.dumps({'toolUseId':'tool-b','finished':True}))
        c = Collector(self.root, processes=lambda:{123:'start'})
        result = c.snapshot()
        nodes = {n['id']:n for n in result['nodes']}
        self.assertEqual(nodes[sid + ':a']['parentId'], sid)
        self.assertEqual(nodes[sid + ':b']['parentId'], sid + ':a')
        self.assertEqual(nodes[sid]['effort']['value'], 'xhigh')
        self.assertIsNone(nodes[sid + ':a']['effort'])
        self.assertEqual(nodes[sid + ':a']['requestedEffort'], 'high')
        self.assertEqual(nodes[sid + ':b']['status'], 'completed')
        self.assertNotIn('params', json.dumps(result))

    def test_reused_pid_is_excluded(self):
        p = self.root / 'sessions/123.json'
        p.parent.mkdir()
        p.write_text(json.dumps({'pid':123,'sessionId':'old','procStart':'old'}))
        self.assertEqual(Collector(self.root, processes=lambda:{123:'new'}).snapshot()['sessions'], [])

    def test_process_start_comparison_uses_registry_utc(self):
        with patch('collector.subprocess.run') as run:
            run.return_value.stdout = '123 Mon Nov 16 05:32:27 2026\n'
            self.assertEqual(process_starts()[123], 'Mon Nov 16 05:32:27 2026')
            self.assertEqual(run.call_args.kwargs['env']['TZ'], 'UTC')

if __name__ == '__main__':
    unittest.main()
