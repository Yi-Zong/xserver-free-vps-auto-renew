import json,os,subprocess,pathlib,tarfile,hashlib
p=pathlib.Path('/opt/xserver'); ev=p/'migration-20261009'
accounts_path=p/'app/xserver_accounts.json'
with tarfile.open('/var/backups/xserver/20261009-migration/prechange.tar.gz') as t:
    original=t.extractfile('opt/xserver/app/xserver_accounts.json').read()
assert original==accounts_path.read_bytes()
accounts=json.loads(original);assert len(accounts)==3
chosen=accounts[0]
env={k:v for k,v in os.environ.items() if 'proxy' not in k.lower()}
env.update(EMAIL=chosen['email'],PASSWORD=chosen['password'],ACCOUNT_LABEL=chosen.get('label') or chosen['email'])
# Production notifier is the same entry used by the unchanged random scheduler.
with (ev/'canary-wrapper.log').open('w') as log:
    proc=subprocess.run(['/usr/bin/python3',str(p/'app/run_xserver_notify.py')],cwd=p/'app',env=env,stdout=log,stderr=subprocess.STDOUT)
(ev/'canary-exit.json').write_text(json.dumps({'selected_account_index':0,'accounts_count':len(accounts),'wrapper_process_exit':proc.returncode,'credentials_bytes_unchanged':accounts_path.read_bytes()==original,'other_accounts_launched':0},indent=2))
print('wrapper process exit',proc.returncode)
raise SystemExit(proc.returncode)
