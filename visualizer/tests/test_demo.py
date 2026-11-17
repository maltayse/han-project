import json
import unittest
from unittest.mock import patch
from demo import DemoCollector


class DemoTests(unittest.TestCase):
    def test_demo_is_synthetic_and_does_not_read_files(self):
        with patch('builtins.open',side_effect=AssertionError('demo must not read files')):
            data=DemoCollector().snapshot()
        self.assertEqual(data['root'],'synthetic-demo')
        self.assertEqual(len(data['sessions']),4)
        self.assertEqual(len(data['nodes']),12)
        self.assertTrue(all(s['name'].startswith('DEMO') for s in data['sessions']))
        self.assertTrue(all(n['model']['source']=='synthetic demo' for n in data['nodes']))
        by_id={n['id']:n for n in data['nodes']}
        self.assertEqual(by_id['demo-scout']['agentType'],'han-scout')
        self.assertEqual(by_id['demo-deep']['agentType'],'han-deep')
        self.assertEqual(by_id['demo-tests']['outcome'],'failed')
        self.assertEqual(data['handoffs'][0]['phase'],'received')
        json.dumps(data)

if __name__ == '__main__':unittest.main()
