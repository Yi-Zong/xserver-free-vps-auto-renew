from pathlib import Path
p=Path('/opt/xserver/app/main.py')
s=Path('/opt/xserver/migration-20261009/source/verified_single.py').read_text()
s=s.replace("from urllib.parse import urlparse\n",'')
s=s.replace("RUN_DIR = os.getenv('RUN_DIR', '/opt/extend-vps-exp')", "os.umask(0o077)\nfor key in list(os.environ):\n    if 'proxy' in key.lower():\n        os.environ.pop(key)\nRUN_DIR = os.environ['RUN_DIR']")
s=s.replace("    proxy_server = os.getenv('PROXY_SERVER')\n",'')
s=s.replace("logging.info('Account: 727****@gmail.com')", "logging.info('Account: local configured account (redacted)')")
s=s.replace("'account':'727****@gmail.com'", "'account':'local-configured-account'")
s=s.replace("os.getenv('GEOIP', 'true')", "os.getenv('GEOIP', 'false')")
a=s.index('    if proxy_server:');b=s.index("    logging.info('Launching Camoufox",a)
s=s[:a]+"    options['firefox_user_prefs'] = {'network.proxy.type': 0}\n    logging.info('Network: direct; proxy environment removed; Firefox proxy type=0')\n\n"+s[b:]
s=s.replace('aiohttp.ClientSession()', 'aiohttp.ClientSession(trust_env=False)')
a=s.index("            logging.error('Session retained");b=s.index('            sys.exit(1)',a)
s=s[:a]+s[b:]
p.write_text(s)

p=Path('/opt/xserver/app/run_xserver_notify.py');s=p.read_text();s=s.replace('with request.urlopen(req, timeout=timeout) as resp:', 'with request.build_opener(request.ProxyHandler({})).open(req, timeout=timeout) as resp:')
a=s.index('def run_xserver_once(')
s=s[:a]+'''RUNS_DIR = Path('/opt/xserver/runs')


def main():
    os.umask(0o077)
    email = os.getenv('EMAIL', '').strip()
    password = os.getenv('PASSWORD', '')
    label = os.getenv('ACCOUNT_LABEL', email or 'unknown')
    if not email or not password:
        raise SystemExit('EMAIL/PASSWORD missing')
    run_dir = RUNS_DIR / (datetime.now().strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8])
    run_dir.mkdir(parents=True, mode=0o700)
    run_env = {k:v for k,v in os.environ.items() if 'proxy' not in k.lower()}
    run_env.update(EMAIL=email, PASSWORD=password, RUN_DIR=str(run_dir), GEOIP='false', DEBUG='false',
                   CAPTCHA_API='https://jp--xserver--fmyy8zpzrgwf.code.run/')
    cmd = ['xvfb-run', '-a', str(WORKSPACE / '.venv/bin/python'), '-u', str(WORKSPACE / 'main.py')]
    core_rc = 1
    try:
        proc = subprocess.run(cmd, cwd=WORKDIR, capture_output=True, text=True, timeout=900, env=run_env)
        core_rc = proc.returncode
        output = (proc.stdout or '') + (proc.stderr or '')
    except subprocess.TimeoutExpired as exc:
        output = 'Core timeout; no automatic retry (avoid duplicate submission).'
    except Exception as exc:
        output = 'Core failed: ' + type(exc).__name__
    (run_dir / 'run.log').write_text(output)
    logged_in = (run_dir / 'login-result.json').exists() and json.loads((run_dir / 'login-result.json').read_text()).get('logged_in') is True
    def read(path):
        return path.read_text() if path.exists() else ''
    results = []
    for server in sorted(run_dir.glob('server-*')):
        if not server.is_dir():
            continue
        r=classify_business(read(server/'RESULT.txt'),read(server/'detail-before.txt'),read(server/'detail-after.txt'),logged_in)
        r.update(server=server.name, provider_result=read(server/'RESULT.txt'))
        results.append(r)
    run_ok = core_rc == 0 and bool(results) and all(r['run_ok'] for r in results)
    need_sign = not results or any(r['need_sign'] for r in results)
    renewed = sum(r['status']=='RENEWED_VERIFIED' for r in results)
    sign_status = ('RENEWED_VERIFIED：已核实新增续期' if renewed else 'NOT_ELIGIBLE：未到窗口，未新增续期') if run_ok else 'FAILED：运行或业务核验失败，未确认新增续期'
    expiry = '; '.join(r['expiry_before']+' → '+r['expiry_after'] for r in results) or '未知'
    shots = sorted(run_dir.rglob('*.png'), key=lambda p:p.stat().st_mtime)
    screenshot = shots[-1] if shots else run_dir/'failure-result.png'
    if not shots:
        from PIL import Image, ImageDraw
        img=Image.new('RGB',(1000,360),'#152033')
        draw=ImageDraw.Draw(img)
        draw.text((40,50),'XServer renewal result',fill='white')
        draw.text((40,120),'FAILED - see notification caption and run evidence',fill='#ff8080')
        draw.text((40,200),datetime.now().isoformat(),fill='white')
        img.save(screenshot)
    msg=build_message(label,run_ok,need_sign,sign_status,expiry,screenshot_path=str(screenshot))
    receipt={'ok':False}
    try:
        payload=json.loads(tg_send_photo(str(screenshot),msg))
        receipt={'ok':payload.get('ok') is True,'message_id':payload.get('result',{}).get('message_id')}
        if not receipt['ok'] or not receipt['message_id']:
            raise RuntimeError('Telegram photo response not confirmed')
    except Exception as exc:
        receipt['error_type']=type(exc).__name__
    exit_code=0 if run_ok and receipt['ok'] and receipt.get('message_id') else 1
    result={'run_ok':run_ok,'need_sign':need_sign,'sign_status':sign_status,'expiry':expiry,
            'logged_in':logged_in,'servers':results,'core_exit_code':core_rc,'wrapper_exit_code':exit_code,
            'telegram':receipt,'sent_via':'telegram-photo' if receipt['ok'] else 'photo-failed',
            'screenshot_path':str(screenshot),'run_dir':str(run_dir),'attempts':1,'retry_attempted':False,
            'network':{'proxy_env':[],'browser_proxy_type':0,'captcha_trust_env':False,'notification_proxy_handler':{}}}
    (run_dir/'notification-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    Path(LOG_DIR).mkdir(parents=True,exist_ok=True)
    log_path=Path(LOG_DIR)/('xserver_'+re.sub(r'[^a-zA-Z0-9_.-]+','_',label)+'.log')
    with log_path.open('a') as f:
        f.write('\\n'+json.dumps(result,ensure_ascii=False)+'\\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
'''
p.write_text(s)
