import pathlib,json,tarfile,hashlib,subprocess,sys
root=pathlib.Path('/opt/xserver');ev=root/'migration-20261009'
sys.path.insert(0,str(root/'app'))
import run_xserver_random_window as s
from datetime import datetime,timedelta
report={}
with tarfile.open('/var/backups/xserver/20261009-migration/prechange.tar.gz') as tar:
    paths=['opt/xserver/app/xserver_accounts.json','opt/xserver/app/run_xserver_random_window.py','etc/systemd/system/xserver-checkin@.service','etc/systemd/system/xserver-checkin-afternoon.timer','etc/systemd/system/xserver-checkin-evening.timer']
    report['preserved']={name:tar.extractfile(name).read()==pathlib.Path('/'+name).read_bytes() for name in paths}
    accounts=json.loads(tar.extractfile(paths[0]).read())
report['account_count']=len(accounts)
report['windows']=s.WINDOWS
report['random_tests']=[]
for name in ['afternoon','evening']:
    sh,sm,eh,em=s.WINDOWS[name]
    start=datetime(2026,10,10,sh,sm,tzinfo=s.TZ);end=start.replace(hour=eh,minute=em)
    for _ in range(1000):
        times=[t for t,_ in s.pick_run_times(accounts,start,end)]
        assert len(times)==3 and len(set(times))==3 and all(start<=t<end for t in times)
    report['random_tests'].append({'window':name,'trials':1000,'inside_window':True,'distinct_slots':True})
report['units']=subprocess.run(['systemctl','list-timers','--all','--no-pager','xserver*'],capture_output=True,text=True).stdout
report['enabled']=subprocess.run(['systemctl','is-enabled','xserver-checkin-afternoon.timer','xserver-checkin-evening.timer'],capture_output=True,text=True).stdout
report['active']=subprocess.run(['systemctl','is-active','xserver-checkin-afternoon.timer','xserver-checkin-evening.timer'],capture_output=True,text=True).stdout
report['timestamp']=subprocess.run(['date','-Is'],capture_output=True,text=True).stdout.strip()
(ev/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
