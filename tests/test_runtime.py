import concurrent.futures
import subprocess
import tempfile
import unittest
from pathlib import Path
from han_runtime.store import Store, Conflict


def claim(directory,handoff,who):
    try:
        Store(directory).receive(handoff,who)
        return True
    except Conflict:
        return False


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.repo=self.base/'repo';self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.name','QA'],check=True)
        subprocess.run(['git','-C',str(self.repo),'config','user.email','qa@example.invalid'],check=True)
        (self.repo/'code.txt').write_text('one\n')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','base'],check=True)
        self.store=Store(self.base/'state');self.task=self.store.start(self.repo,'source','QA task')
        self.evidence=self.base/'state/tests.txt';self.evidence.write_text('validation: passed')
        self.reviewlog=self.base/'state/review.txt';self.reviewlog.write_text('independent inspection: pass')

    def attempt(self,agent='worker'):
        return self.store.register(self.task,'source',agent,'han-builder')

    def prepare(self):
        return self.store.prepare(self.task,'source',['Verify worktree','Continue next task'])

    def test_read_only_missing_store_does_not_create_directory(self):
        missing=self.base/'missing';self.assertEqual(Store(missing).overview()['tasks'],[])
        self.assertFalse(missing.exists())

    def test_state_inside_repository_is_rejected(self):
        with self.assertRaises(Conflict):Store(self.repo/'private-state').start(self.repo,'source','Task')
        self.assertFalse((self.repo/'private-state').exists())

    def test_role_defaults_and_three_worker_limit(self):
        ids=[self.attempt(str(i)) for i in range(3)]
        with self.assertRaises(Conflict):self.attempt('fourth')
        rows=self.store.overview()['attempts']
        self.assertEqual((rows[0]['model'],rows[0]['effort']),('sonnet','medium'))
        self.assertEqual(len(ids),3)
        other=self.store.start(self.repo,'source','Another task')
        with self.assertRaises(Conflict):self.store.register(other,'source','fourth','han-builder')

    def test_no_self_review_and_no_worker_self_accept(self):
        a=self.attempt();self.store.result(a,'source','ready','Implemented',[self.evidence])
        with self.assertRaises(Conflict):self.store.review(a,'source','worker','pass',[self.reviewlog])
        with self.assertRaises(Conflict):self.store.accept(a,'worker')
        with self.assertRaises(Conflict):self.store.accept(a,'source')

    def test_ready_is_not_accepted(self):
        a=self.attempt();self.store.result(a,'source','ready','Implemented',[self.evidence])
        self.assertEqual(self.store.overview()['attempts'][0]['outcome'],'ready')
        self.store.review(a,'source','independent-reviewer','pass',[self.reviewlog])
        self.store.accept(a,'source')
        self.assertEqual(self.store.overview()['attempts'][0]['outcome'],'accepted')
        with self.assertRaises(Conflict):self.store.accept(a,'source')

    def test_failed_result_cannot_be_accepted(self):
        for outcome in ('blocked','failed'):
            a=self.attempt(outcome);self.store.result(a,'source',outcome,'Tests failed',[self.evidence])
            with self.assertRaises(Conflict):self.store.accept(a,'source')

    def test_changed_evidence_prevents_acceptance(self):
        a=self.attempt();self.store.result(a,'source','ready','Implemented',[self.evidence])
        self.store.review(a,'source','reviewer','pass',[self.reviewlog])
        self.evidence.write_text('different')
        with self.assertRaises(Conflict):self.store.accept(a,'source')

    def test_handoff_is_two_phase_and_persists_after_restart(self):
        h=self.prepare();self.assertEqual(self.store.overview()['tasks'][0]['owner'],'source')
        Store(self.store.directory).receive(h,'successor')
        self.assertEqual(self.store.overview()['tasks'][0]['owner'],'source')
        with self.assertRaises(Conflict):self.store.commit(h,'successor')
        self.store.commit(h,'source')
        task=self.store.overview()['tasks'][0]
        self.assertEqual((task['owner'],task['version']),('successor',2))
        with self.assertRaises(Conflict):self.store.commit(h,'source')
        with self.assertRaises(Conflict):self.attempt('stale source')

    def test_checkpoint_does_not_transfer_or_block_new_work(self):
        h=self.store.prepare(self.task,'source',['Continue'],'checkpoint')
        with self.assertRaises(Conflict):self.store.receive(h,'successor')
        self.attempt()
        self.assertEqual(self.store.overview()['tasks'][0]['owner'],'source')

    def test_running_workers_block_receipt_and_pending_transfer_blocks_dispatch(self):
        self.attempt();h=self.prepare()
        with self.assertRaises(Conflict):self.store.receive(h,'successor')
        with self.assertRaises(Conflict):self.attempt('duplicate')
        self.store.cancel(h,'source')
        self.attempt('second worker')

    def test_dirty_byte_changes_after_prepare_and_after_receipt(self):
        dirty=self.repo/'code.txt';dirty.write_text('dirty one')
        h=self.prepare();dirty.write_text('dirty two')
        with self.assertRaises(Conflict):self.store.receive(h,'successor')
        self.store.cancel(h,'source');h=self.prepare();self.store.receive(h,'successor')
        dirty.write_text('dirty three')
        with self.assertRaises(Conflict):self.store.commit(h,'source')

    def test_head_and_index_changes_reject_transfer(self):
        h=self.prepare();(self.repo/'code.txt').write_text('new')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','new'],check=True)
        with self.assertRaises(Conflict):self.store.receive(h,'successor')

    def test_no_duplicate_prepare_or_receive(self):
        h=self.prepare()
        with self.assertRaises(Conflict):self.prepare()
        self.store.receive(h,'successor')
        with self.assertRaises(Conflict):self.store.receive(h,'successor')

    def test_two_successors_race(self):
        h=self.prepare()
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(claim,[self.store.directory]*2,[h]*2,['next-a','next-b']))
        self.assertEqual(sum(results),1)

    def test_missing_or_outside_evidence_is_rejected(self):
        a=self.attempt()
        with self.assertRaises(Conflict):self.store.result(a,'source','ready','done',[self.base/'missing'])
        outside=self.base/'private';outside.write_text('private')
        with self.assertRaises(Conflict):self.store.result(a,'source','ready','done',[outside])

    def test_review_failure_requires_new_attempt(self):
        a=self.attempt();self.store.result(a,'source','ready','Implemented',[self.evidence])
        self.store.review(a,'source','reviewer','changes_requested',[self.reviewlog])
        with self.assertRaises(Conflict):self.store.accept(a,'source')
        with self.assertRaises(Conflict):self.store.result(a,'source','ready','overwriting old result',[self.evidence])
        self.attempt('worker') # same native agent can resume, with a different attempt ID

    def test_attempt_change_after_prepare_requires_fresh_handoff(self):
        a=self.attempt();h=self.prepare()
        self.store.result(a,'source','ready','Returned',[self.evidence])
        with self.assertRaises(Conflict):self.store.receive(h,'successor')

    def test_historical_evidence_survives_log_reuse(self):
        a=self.attempt();self.store.result(a,'source','failed','Initial fail',[self.evidence])
        self.evidence.write_text('second run passed')
        b=self.attempt();self.store.result(b,'source','ready','Fixed',[self.evidence])
        h=self.prepare();self.store.receive(h,'successor')
        rows=self.store.overview()['attempts']
        import json
        first=json.loads(rows[0]['evidence'])[0]
        self.assertEqual(Path(first['path']).read_text(),'validation: passed')

    def test_document_failure_does_not_freeze_task(self):
        directory=self.store.directory/'handoffs';directory.write_text('not a directory')
        with self.assertRaises((OSError,Conflict)):self.prepare()
        self.assertEqual(self.store.overview()['handoffs'],[])
        self.attempt()

    def test_context_note_is_an_immutable_checkpoint_reference(self):
        note=self.store.directory/'note.md';note.write_text('Objective, decision, unrun checks and stop conditions')
        h=self.store.prepare(self.task,'source',['Continue'],'checkpoint',[note])
        row=self.store.overview()['handoffs'][0]
        note.write_text('newer context')
        frozen=Path(row['payload']['context'][0]['path'])
        self.assertIn('Objective',frozen.read_text())
        self.assertIn(str(frozen),self.store.document(h))

    def test_dirty_submodule_is_rejected(self):
        module=self.base/'module';module.mkdir()
        subprocess.run(['git','init','-q',str(module)],check=True)
        subprocess.run(['git','-C',str(module),'config','user.name','QA'],check=True)
        subprocess.run(['git','-C',str(module),'config','user.email','qa@example.invalid'],check=True)
        (module/'file').write_text('base')
        subprocess.run(['git','-C',str(module),'add','.'],check=True)
        subprocess.run(['git','-C',str(module),'commit','-qm','base'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','protocol.file.allow=always','submodule','add','-q',str(module),'module'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qam','module'],check=True)
        (self.repo/'module/file').write_text('changed inside module')
        with self.assertRaises(Conflict):self.prepare()
        for ignore in ('dirty','all'):
            subprocess.run(['git','-C',str(self.repo),'config','submodule.module.ignore',ignore],check=True)
            with self.assertRaises(Conflict):self.prepare()


if __name__=='__main__':unittest.main()
