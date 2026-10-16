import os,json,subprocess,pathlib,time,sys,urllib.parse
os.umask(0o077)
p=pathlib.Path('/opt/extend-vps-exp'); cfg=json.loads(pathlib.Path('/opt/extend-vps-exp/secrets/account-example-account-20261009T065226Z.json').read_text()); r=pathlib.Path('/opt/extend-vps-exp/runs/account-example-account-20261009T065226Z')
os.environ.update({k:v for k,v in cfg.items() if k!='upstream_proxy'})
os.environ.update(DISPLAY=':99',RUN_DIR=str(r),GEOIP='false',PROXY_SERVER='http://127.0.0.1:11081')
import requests
try:
 response=requests.get('https://api.ipify.org',proxies={'https':cfg['upstream_proxy']},timeout=30)
 print('Authenticated SOCKS5 HTTPS egress:',response.status_code,response.text,flush=True)
 response.raise_for_status()
except Exception as e:
 print('Proxy egress failed:',type(e).__name__,flush=True);sys.exit(2)
u=urllib.parse.urlparse(cfg['upstream_proxy']);remote=f'socks5://{u.hostname}:{u.port}#{u.username}:{u.password}'
bridge=subprocess.Popen([sys.executable,'-m','pproxy','-l','http://127.0.0.1:11081','-r',remote],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 import socket
 for _ in range(30):
  try:
   with socket.create_connection(('127.0.0.1',11081),1):break
  except OSError:time.sleep(.2)
 else:raise RuntimeError('local proxy bridge unavailable')
 subprocess.run([sys.executable,'-u',str(r/'verified_single.py')],check=True,cwd=p)
finally:bridge.terminate();bridge.wait(timeout=10)
