import sys, unittest
sys.path.insert(0, '/opt/xserver/app')
import run_xserver_notify as n

class NotificationTests(unittest.TestCase):
    def test_not_due_caption(self):
        msg=n.build_message('账号2',True,False,'NOT_ELIGIBLE：未到窗口，未新增续期','2026-10-10 → 2026-10-10', screenshot_path='/tmp/result.png')
        self.assertIn('状态：暂无需续期',msg)
        self.assertIn('到期日期：2026-10-10',msg)
        self.assertNotIn('NOT_ELIGIBLE',msg)
        self.assertNotIn('→',msg)
        self.assertNotIn('result.png',msg)

    def test_official_window(self):
        msg=n.build_message('账号2',True,False,'NOT_ELIGIBLE','2026-10-10',provider_result='NOT_ELIGIBLE\n利用を継続される場合は、2026年10月10日 12:00以降にお試しください。')
        self.assertIn('下次可续期：2026-10-10 12:00（官网时间）',msg)
        self.assertNotIn('CST',msg)

    def test_verified_success_and_failure(self):
        msg=n.build_message('账号2',True,True,'RENEWED_VERIFIED','2026-10-10 → 2026-10-11')
        self.assertIn('状态：续期成功',msg)
        self.assertIn('到期日期：2026-10-11',msg)
        self.assertNotIn('RENEWED_VERIFIED',msg)
        msg=n.build_message('账号2',False,True,'FAILED','未知')
        self.assertIn('状态：续期失败',msg)
        self.assertIn('原因：',msg)
        self.assertNotIn('续期成功',msg)
        self.assertNotIn('FAILED',msg)

    def test_business_evidence(self):
        before='利用期限 2026年10月10日'
        after='利用期限 2026年10月11日'
        done='SUBMITTED\n利用期限の更新手続きが完了しました'
        cases=[('NOT_ELIGIBLE',before,before,True,'NOT_ELIGIBLE'),(done,before,after,True,'RENEWED_VERIFIED'),(done,before,before,True,'FAILED'),('SUBMITTED',before,after,True,'FAILED'),(done,before,after,False,'FAILED'),('ERROR',before,before,True,'FAILED')]
        for result,old,new,login,status in cases:
            with self.subTest(status=status,result=result,login=login):
                self.assertEqual(n.classify_business(result,old,new,login)['status'],status)

if __name__=='__main__': unittest.main(verbosity=2)
