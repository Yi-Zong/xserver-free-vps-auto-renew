import pathlib,json
items=[]
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        args=(p/'cmdline').read_bytes().split(b'\0')
        if b'/opt/xserver/app/main.py' not in args and not any(b'camoufox-bin' in a for a in args):continue
        env=(p/'environ').read_bytes().split(b'\0')
        proxy=[e.split(b'=')[0].decode() for e in env if b'proxy' in e.split(b'=')[0].lower()]
        items.append({'pid':int(p.name),'executable':args[0].decode(),'proxy_environment_keys':proxy})
        for i,a in enumerate(args):
            if a==b'-profile' and i+1<len(args):
                profile=pathlib.Path(args[i+1].decode())
                prefs=profile/'prefs.js'
                if prefs.exists():
                    items[-1]['proxy_preferences']=[l for l in prefs.read_text().splitlines() if 'network.proxy.' in l]
    except OSError:continue
pathlib.Path('/opt/xserver/migration-20261009/live-network.json').write_text(json.dumps(items,indent=2))
print(json.dumps(items,indent=2))
