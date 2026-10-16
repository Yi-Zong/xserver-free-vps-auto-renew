import os, sys, json, subprocess, pathlib, hashlib, fcntl
from datetime import datetime
os.umask(0o077)
p=pathlib.Path('/opt/xserver'); ev=p/'notification-polish-20261009'
lock=(ev/'manual.lock').open('w'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
idx=int(sys.argv[1]); assert idx in (1,2), 'index0 is forbidden'
record=ev/f'index{idx}-exit.json'
assert not record.exists(), 'already executed; do not repeat'
for name in ('afternoon','evening'):
    state=subprocess.run(['systemctl','is-active',f'xserver-checkin@{name}.service'],capture_output=True,text=True).stdout.strip()
    assert state not in ('active','activating','deactivating'), 'batch conflict: abort without modifying timer'
for proc in pathlib.Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name)==os.getpid(): continue
    try: argv=(proc/'cmdline').read_bytes().split(b'\0')
    except (OSError,PermissionError): continue
    assert not any(a in (b'/opt/xserver/app/main.py',b'/opt/xserver/app/run_xserver_notify.py',b'/opt/xserver/app/run_xserver_random_window.py') for a in argv), 'existing worker: abort'
original=(p/'app/xserver_accounts.json').read_bytes(); accounts=json.loads(original); assert len(accounts)==3
chosen=accounts[idx]; label=str(chosen.get('label') or chosen['email']); masked=label[:3]+'****'
env={k:v for k,v in os.environ.items() if 'proxy' not in k.lower()}
env.update(EMAIL=chosen['email'],PASSWORD=chosen['password'],ACCOUNT_LABEL=masked)
started=datetime.now().isoformat(); prior=set((p/'runs').iterdir())
with (ev/f'index{idx}-wrapper.log').open('x') as log:
    result=subprocess.run(['/usr/bin/python3',str(p/'app/run_xserver_notify.py')],cwd=p/'app',env=env,stdout=log,stderr=subprocess.STDOUT)
runs=[str(x) for x in set((p/'runs').iterdir())-prior]
data={'selected_account_index':idx,'label':masked,'started':started,'finished':datetime.now().isoformat(),'wrapper_process_exit':result.returncode,'credentials_bytes_unchanged':original==(p/'app/xserver_accounts.json').read_bytes(),'run_dirs':runs,'attempts':1,'index0_launched':False}
record.write_text(json.dumps(data,ensure_ascii=False,indent=2)); print(json.dumps(data,ensure_ascii=False)); sys.exit(result.returncode)
