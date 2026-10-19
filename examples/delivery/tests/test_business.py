"""Business constraints independent from graph projection and expected JSON."""
import json
from pathlib import Path
import sys
import threading
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.service import Delivery
from app.store import Store
from app.ports import Events
from app.workflow import advance
from app.checks import run_checks


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.store=Store();self.app=Delivery(self.store);self.app.command('grant',id='G1',expires=200)

    def tearDown(self):self.store.close()

    def test_types_and_invalid_edits(self):
        for value in ('',True,4000,'x'*4097):
            with self.assertRaises((TypeError,ValueError)):self.app.command('edit',content=value)
        for value in (-1,True,'now'):
            with self.assertRaises((TypeError,ValueError)):self.app.command('clock',clock=value)
        self.assertEqual(self.store.snapshot()['param_version'],1)

    def test_no_illegal_jump(self):
        with self.assertRaises(Exception):advance('draft','publish')
        self.assertEqual(len(self.app.commit()['effects']),0)

    def test_probe_callback_failure(self):
        def broken(*_):raise RuntimeError('sink')
        self.app.events=Events(broken)
        self.assertEqual(self.app.execute()['state'],'completed')
        self.assertGreater(self.app.events.errors,0)

    def test_off_does_not_evaluate_payload(self):
        events=Events()
        def broken():raise AssertionError('evaluated disabled payload')
        events.emit('ignored','return',broken)
        self.assertEqual(events.errors,0)

    def test_transaction_rollback_and_retry(self):
        self.app.prepare();original=self.store.artifact
        def broken(*_):
            original(*_);raise OSError('disk fault after insert')
        self.store.artifact=broken
        with self.assertRaises(OSError):self.app.commit()
        self.assertEqual(len(self.store.snapshot()['effects']),0)
        self.assertEqual(self.store.snapshot()['state'],'ready')
        self.store.artifact=original
        self.assertEqual(len(self.app.commit()['effects']),1)

    def test_edit_while_worker_running(self):
        started=threading.Event();release=threading.Event()
        def worker(content,**kwargs):
            started.set();self.assertTrue(release.wait(5));return run_checks(content,**kwargs)
        self.app.checker=worker
        thread=threading.Thread(target=self.app.prepare);thread.start()
        self.assertTrue(started.wait(5));self.app.command('edit',content='changed during execution')
        release.set();thread.join(5);self.assertFalse(thread.is_alive())
        self.assertNotEqual(self.app.commit()['state'],'completed')
        self.assertEqual(len(self.store.snapshot()['effects']),0)

    def test_second_version_has_separate_effect(self):
        self.app.execute();self.app.command('edit',content='second')
        self.app.command('grant',id='G2',expires=200)
        self.assertEqual([a['version'] for a in self.app.execute()['effects']],[1,2])

    def test_old_worker_cannot_overwrite_new_attempt(self):
        started=threading.Event();release=threading.Event();errors=[]
        def worker(content,**kwargs):
            if content=='public sample':
                started.set();release.wait(4)
            return run_checks(content,**kwargs)
        self.app.checker=worker
        def old_attempt():
            try:self.app.prepare()
            except Exception as exc:errors.append(str(exc))
        thread=threading.Thread(target=old_attempt);thread.start();self.assertTrue(started.wait(3))
        try:
            self.app.command('edit',content='new attempt')
            self.app.command('grant',id='G2',expires=200)
            self.assertEqual(self.app.execute()['state'],'completed')
        finally:release.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual([a['version'] for a in self.store.snapshot()['effects']],[2])
        self.assertEqual(self.store.snapshot()['state'],'completed')

    def test_cancel_during_checks_releases_resources(self):
        started=threading.Event();release=threading.Event();errors=[]
        def checker(content,**kwargs):
            def hook(_):started.set();release.wait(4)
            return run_checks(content,task_hook=hook,**kwargs)
        self.app.checker=checker
        def prepare():
            try:self.app.prepare()
            except Exception as exc:errors.append(str(exc))
        thread=threading.Thread(target=prepare);thread.start();self.assertTrue(started.wait(3))
        self.app.command('cancel');release.set();thread.join(5)
        result=self.app.commit()
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(result['state'],'cancelled');self.assertEqual(result['effects'],[])
        self.assertEqual(result['execution']['resources']['workers']['available'],2)

    def test_retry_does_not_show_previous_attempt_facts(self):
        self.app.prepare();self.app.command('revoke',id='G1');self.app.commit()
        self.app.command('grant',id='G2',expires=200)
        started=threading.Event();release=threading.Event();errors=[]
        def checker(content,**kwargs):
            started.set();release.wait(4);return run_checks(content,**kwargs)
        self.app.checker=checker
        def prepare():
            try:self.app.prepare()
            except Exception as exc:errors.append(str(exc))
        thread=threading.Thread(target=prepare);thread.start();self.assertTrue(started.wait(3))
        try:
            current=self.store.snapshot()
            self.assertEqual(current['state'],'checking')
            self.assertEqual(current['execution']['activities'],{'checksum':'pending','privacy':'pending'})
            self.assertEqual(current['execution']['revision'],0)
            self.assertEqual(current['checks'],{});self.assertIsNone(current['prepared_version'])
        finally:release.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])

    def test_persistent_restart(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as folder:
            path=str(Path(folder)/'business.sqlite');first=Store(path)
            a=Delivery(first);a.command('grant',id='G',expires=200);a.execute();first.close()
            second=Store(path)
            try:self.assertEqual(len(Delivery(second).execute()['effects']),1)
            finally:second.close()


if __name__=='__main__':unittest.main()
