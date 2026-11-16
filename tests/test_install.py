import tempfile
import unittest
import subprocess
import json
from pathlib import Path
from install import install, FILES


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'.claude'

    def test_dry_run_and_repeat(self):
        self.assertEqual(len(install(self.root,dry_run=True)),len(FILES))
        self.assertFalse(self.root.exists())
        self.assertEqual(len(install(self.root)),len(FILES))
        self.assertEqual(install(self.root),[])
        self.assertFalse((self.root/'settings.json').exists())

    def test_conflict_never_partially_installs(self):
        p=self.root/FILES[-1];p.parent.mkdir(parents=True);p.write_text('custom agent')
        with self.assertRaises(ValueError):install(self.root)
        self.assertFalse((self.root/FILES[0]).exists())
        self.assertEqual(p.read_text(),'custom agent')

    def test_force_preserves_backup(self):
        install(self.root)
        p=self.root/FILES[0];p.write_text('custom skill')
        self.assertEqual(len(install(self.root,force=True)),1)
        backups=list((self.root/'han-project-backups').glob('*/skills/han-project/SKILL.md'))
        self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_text(),'custom skill')

    def test_symlink_escape(self):
        self.root.mkdir()
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (self.root/'skills').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):install(self.root)
        self.assertEqual(list(outside.iterdir()),[])

    def test_force_backup_cannot_escape_target(self):
        install(self.root)
        skill=self.root/FILES[0];skill.write_text('private local changes')
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (self.root/'han-project-backups').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):install(self.root,force=True)
        self.assertEqual(list(outside.iterdir()),[])
        self.assertEqual(skill.read_text(),'private local changes')

    def test_installed_runtime_works_without_source_imports(self):
        install(self.root)
        state=Path(self.tmp.name)/'state'
        p=subprocess.run(['python3',str(self.root/'han-project-runtime/han.py'),'--state-dir',str(state),'status'],
                         cwd=self.tmp.name,capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['tasks'],[])
        self.assertFalse(state.exists())

if __name__ == '__main__':unittest.main()
