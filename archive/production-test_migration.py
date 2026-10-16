import unittest
import run_xserver_notify as n

class ResultTests(unittest.TestCase):
    def test_not_eligible_is_not_new_renewal(self):
        self.assertTrue(hasattr(n, 'classify_business'), 'structured business classifier missing')
        r=n.classify_business('NOT_ELIGIBLE\n12時間前から', '利用期限 2026年10月10日', '利用期限 2026年10月10日', True)
        self.assertEqual(r['status'], 'NOT_ELIGIBLE')
        self.assertFalse(r['need_sign'])
        self.assertTrue(r['run_ok'])

    def test_verified_requires_confirmation_and_increasing_expiry(self):
        for result, after, login, expected in [
            ('SUBMITTED\n利用期限の更新手続きが完了しました。', '利用期限 2026年10月10日', True, 'RENEWED_VERIFIED'),
            ('SUBMITTED\n利用期限の更新手続きが完了しました。', '利用期限 2026年10月09日', True, 'FAILED'),
            ('SUBMITTED', '利用期限 2026年10月10日', True, 'FAILED'),
            ('SUBMITTED\n利用期限の更新手続きが完了しました。', '利用期限 2026年10月10日', False, 'FAILED'),
            ('ERROR', '', False, 'FAILED'),
            ('NOT_ELIGIBLE', '', False, 'FAILED'),
        ]:
            with self.subTest(result=result,after=after,login=login):
                self.assertEqual(n.classify_business(result,'利用期限 2026年10月09日',after,login)['status'],expected)

    def test_notification_keeps_layout_but_explains_business_result(self):
        msg=n.build_message('account1',True,False,'NOT_ELIGIBLE：未到窗口，未新增续期','2026年10月10日',screenshot_path='result.png')
        self.assertIn('🖥 XServer 续期结果',msg)
        self.assertIn('⚪️ 今天无需续期',msg)
        self.assertIn('未新增续期',msg)
        self.assertIn('2026年10月10日',msg)

    def test_wrapper_records_real_photo_receipt_and_failure_exit(self):
        from unittest.mock import patch
        import tempfile, pathlib, json, os, subprocess
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            def fake_run(cmd, **kw):
                self.assertEqual(cmd[0], 'xvfb-run')
                self.assertNotIn('HTTP_PROXY', kw['env'])
                self.assertNotIn('PROXY_SERVER', kw['env'])
                self.assertEqual(kw['env']['GEOIP'], 'false')
                rd=pathlib.Path(kw['env']['RUN_DIR'])
                (rd/'RESULT.txt').write_text('ERROR\nlogin failed')
                return subprocess.CompletedProcess(cmd,1,'','')
            with patch.dict(os.environ, {'EMAIL':'account@example.invalid','PASSWORD':'notreal','HTTP_PROXY':'http://invalid','PROXY_SERVER':'http://invalid'}), patch.object(n,'RUNS_DIR',root,create=True), patch.object(n,'LOG_DIR',td), patch.object(n.subprocess,'run',side_effect=fake_run) as run, patch.object(n,'tg_send_photo',return_value=json.dumps({'ok':True,'result':{'message_id':123}})):
                rc=n.main()
                self.assertEqual(rc,1)
                self.assertEqual(run.call_count,1)
                reports=list(root.glob('*/notification-result.json'))
                self.assertEqual(len(reports),1)
                self.assertEqual(json.loads(reports[0].read_text())['telegram']['message_id'],123)

if __name__ == '__main__': unittest.main()
