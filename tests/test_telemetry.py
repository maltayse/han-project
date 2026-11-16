import unittest
from han_runtime.telemetry import WorkflowCollector


class Native:
    def snapshot(self):
        return dict(sessions=[],nodes=[],errors=[])


class State:
    def overview(self):
        return dict(tasks=[dict(id='t1',owner='successor',title='Task',repo='/demo')],attempts=[],events=[],
                    handoffs=[dict(id='h1',task='t1',source='source',target='successor',kind='transfer',version=1,
                                   phase='committed',created=1,payload=dict(title='Task',nextSteps=['Continue']))])


class TelemetryTests(unittest.TestCase):
    def test_closed_source_is_preserved_only_as_record(self):
        result=WorkflowCollector(Native(),State()).snapshot()
        source=next(n for n in result['nodes'] if n['id']=='source')
        self.assertEqual(source['status'],'recorded')
        self.assertIsNone(source['model'])
        self.assertTrue(source['historical'])
        self.assertEqual(result['handoffs'][0]['phase'],'committed')
        self.assertEqual(len(result['sessions']),2)

    def test_broken_store_does_not_hide_native_telemetry(self):
        class Broken:
            def overview(self):raise ValueError('broken')
        result=WorkflowCollector(Native(),Broken()).snapshot()
        self.assertEqual(result['handoffs'],[])
        self.assertIn('ValueError',result['errors'][0])

if __name__=='__main__':unittest.main()
