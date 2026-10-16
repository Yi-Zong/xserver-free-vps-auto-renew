"""Offline regression tests. No production imports, credentials or requests."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'app' / (name + '.py'))
    obj = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, {'TG_BOT_TOKEN': '', 'TG_CHAT_ID': ''}):
        spec.loader.exec_module(obj)
    return obj

n = module('run_xserver_notify')
s = module('run_xserver_random_window')

class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.net = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden'))
        self.net.start()
        self.addCleanup(self.net.stop)

    def test_verified_business_requires_all_evidence(self):
        old, new = '利用期限 2026年10月10日', '利用期限 2026年10月11日'
        done = 'SUBMITTED\n利用期限の更新手続きが完了しました'
        cases = [(done, new, True, 'RENEWED_VERIFIED'), (done, old, True, 'FAILED'),
                 ('SUBMITTED', new, True, 'FAILED'), (done, new, False, 'FAILED'),
                 ('NOT_ELIGIBLE', old, True, 'NOT_ELIGIBLE'), ('NOT_ELIGIBLE', new, True, 'FAILED'),
                 ('ERROR', '', False, 'FAILED')]
        for result, after, login, expected in cases:
            with self.subTest(result=result, after=after, login=login):
                self.assertEqual(n.classify_business(result, old, after, login)['status'], expected)

    def test_caption_preserves_current_user_contract(self):
        for ok, need, rc, expected in [(True, True, 0, '✅ 续期成功'), (True, False, 0, '🌿 暂无需续期'),
                                      (False, True, 0, '❌ 未确认续期成功'), (False, True, 1, '⚠️ 未完成核验')]:
            msg = n.build_message('account1@example.invalid', ok, need, 'INTERNAL_ENUM',
                                  '2026-10-10 → 2026-10-11', screenshot_path='result.png', core_exit_code=rc)
            self.assertIn('account1@example.invalid', msg)
            self.assertIn('脚本运行：', msg)
            self.assertIn('账号续期：' + expected, msg)
            for forbidden in ['INTERNAL_ENUM', '2026-', '→', 'result.png', '到期']:
                self.assertNotIn(forbidden, msg)

    def test_random_times_in_both_windows(self):
        rng = random.Random(42)
        accounts = [{'email': f'account{i}@example.invalid'} for i in range(3)]
        with patch.object(s.random, 'randint', side_effect=rng.randint):
            for name in ['afternoon', 'evening']:
                sh, sm, eh, em = s.WINDOWS[name]
                start = datetime(2026, 1, 1, sh, sm, tzinfo=s.TZ)
                end = start.replace(hour=eh, minute=em)
                for _ in range(1000):
                    plan = s.pick_run_times(accounts, start, end)
                    self.assertEqual(len(plan), 3)
                    self.assertEqual(len({t for t, _ in plan}), 3)
                    self.assertTrue(all(start <= t < end for t, _ in plan))
                    self.assertEqual(plan, sorted(plan, key=lambda x: x[0]))

    def test_no_credential_defaults(self):
        self.assertEqual(n.BOT_TOKEN, '')
        self.assertEqual(n.CHAT_ID, '')
        self.assertEqual(s.TG_BOT_TOKEN, '')
        self.assertEqual(s.TG_CHAT_ID, '')

    def test_config_schema(self):
        accounts = json.loads((ROOT / 'app/xserver_accounts.example.json').read_text())
        self.assertEqual(len(accounts), 3)
        for acc in accounts:
            self.assertEqual(set(acc), {'email', 'password', 'label', 'log'})
            self.assertTrue(acc['email'].endswith('@example.invalid'))
            self.assertEqual(Path(acc['log']).name, acc['log'])

    def test_photo_request_contract(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'image.png'
            p.write_bytes(b'fake image used only by mocked transport')
            def transport(url, data, headers, timeout):
                self.assertTrue(url.endswith('/sendPhoto'))
                self.assertIn(b'name="photo"', data)
                self.assertIn(b'name="caption"', data)
                self.assertIn(b'name="chat_id"', data)
                self.assertEqual(timeout, 60)
                return '{"ok":true,"result":{"message_id":1}}', {}
            with patch.object(n, 'http_post', side_effect=transport):
                self.assertTrue(json.loads(n.tg_send_photo(str(p), 'caption'))['ok'])

    def test_legacy_image_upload_contract(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'image.png'
            p.write_bytes(b'fake')
            def transport(url, data, headers, timeout):
                self.assertIn(b'name="file"', data)
                self.assertIn(b'name="strategy_id"', data)
                self.assertEqual(headers['Origin'], n.UPLOAD_REFERER)
                self.assertEqual(timeout, 90)
                return '{"data":{"url":"https://example.invalid/image.png"}}', {}
            with patch.object(n, 'http_post', side_effect=transport):
                self.assertEqual(n.upload_image_to_111666best(str(p))[0], 'https://example.invalid/image.png')

    def test_wrapper_business_and_photo_receipt_exit(self):
        for core_rc, business, receipt, expected in [
            (0, True, {'ok': True, 'result': {'message_id': 1}}, 0),
            (0, True, {'ok': False}, 1),
            (0, True, {'ok': True, 'result': {}}, 1),
            (0, False, {'ok': True, 'result': {'message_id': 1}}, 1),
            (1, False, {'ok': True, 'result': {'message_id': 1}}, 1),
        ]:
            with self.subTest(core_rc=core_rc, business=business, receipt=receipt), tempfile.TemporaryDirectory() as td:
                def fake_run(cmd, **kw):
                    self.assertEqual(cmd[0], 'xvfb-run')
                    self.assertFalse(any('proxy' in k.lower() for k in kw['env']))
                    rd = Path(kw['env']['RUN_DIR'])
                    (rd / 'image.png').write_bytes(b'fake')
                    if business:
                        (rd / 'login-result.json').write_text('{"logged_in":true}')
                        server = rd / 'server-example'
                        server.mkdir()
                        (server / 'RESULT.txt').write_text('NOT_ELIGIBLE\nofficial notice')
                        for field in ['detail-before.txt', 'detail-after.txt']:
                            (server / field).write_text('利用期限 2026年10月10日')
                    return subprocess.CompletedProcess(cmd, core_rc, '', '')
                with patch.dict(os.environ, {'EMAIL': 'account1@example.invalid', 'PASSWORD': 'fake', 'HTTP_PROXY': 'http://example.invalid'}), \
                     patch.object(n, 'RUNS_DIR', Path(td)), patch.object(n, 'LOG_DIR', td), \
                     patch.object(n.subprocess, 'run', side_effect=fake_run) as runner, \
                     patch.object(n, 'tg_send_photo', return_value=json.dumps(receipt)), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(n.main(), expected)
                    self.assertEqual(runner.call_count, 1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
