import re
import unittest
from pathlib import Path
from han_runtime.store import ROLES


class RoleContractTests(unittest.TestCase):
    def test_routing_defaults_match_actual_agent_definitions(self):
        root=Path(__file__).resolve().parents[1]
        for role,(model,effort) in ROLES.items():
            text=(root/'agents'/(role+'.md')).read_text()
            front=text.split('---',2)[1]
            fields=dict(re.findall(r'^(\w+): (.+)$',front,re.M))
            self.assertEqual((fields['model'],fields['effort']),(model,effort))
            tools={s.strip() for s in fields['tools'].split(',')}
            self.assertNotIn('Agent',tools,'Workers must not spawn workers/reviewers')
            if role in ('han-scout','han-reviewer','han-advisor'):
                self.assertEqual(tools,{'Read','Glob','Grep'})
                self.assertNotIn('run integrated tests',text)
            self.assertIn('coordinator',text)

if __name__=='__main__':unittest.main()
