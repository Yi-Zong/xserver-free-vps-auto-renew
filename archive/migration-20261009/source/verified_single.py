import asyncio
import json
import os
import sys
import logging
import aiohttp
from urllib.parse import urlparse
import camoufox.fingerprints as cf_fp
import camoufox.utils as cf_utils
from camoufox.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from playwright_captcha import CaptchaType, ClickSolver, FrameworkType
from playwright_captcha.utils.camoufox_add_init_script.add_init_script import get_addon_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

RUN_DIR = os.getenv('RUN_DIR', '/opt/extend-vps-exp')
os.makedirs(RUN_DIR, exist_ok=True)


def _generate_fingerprint(*args, **kwargs):
    try:
        return _orig_generate(*args, **kwargs)
    except Exception as exc:
        if kwargs.get('screen') is not None and type(exc).__name__ in ('InvalidConstraints', 'RestrictiveConstraints'):
            logging.warning('Dropping screen constraint after %s', type(exc).__name__)
            kwargs['screen'] = None
            return _orig_generate(*args, **kwargs)
        raise


_orig_generate = cf_fp.generate_fingerprint
cf_fp.generate_fingerprint = _generate_fingerprint
cf_utils.generate_fingerprint = _generate_fingerprint


async def shot(page, name):
    path = os.path.join(RUN_DIR, name)
    try:
        await page.screenshot(path=path, full_page=True)
        logging.info('Screenshot %s url=%s', path, page.url)
    except Exception as exc:
        logging.warning('Screenshot %s failed: %s', name, exc)


async def turnstile_token(page):
    return await page.evaluate('''() => {
        const el = document.querySelector('[name="cf-turnstile-response"]');
        return el && el.value ? el.value : '';
    }''')


async def solve_turnstile(page, framework, label):
    """Same method the project uses on the renewal page: ClickSolver + CLOUDFLARE_TURNSTILE.

    The widget often shows 成功しました and writes cf-turnstile-response before the
    solver notices div#success inside the cross-origin iframe, so a token is success.
    """
    logging.info('Solving %s Turnstile with project ClickSolver...', label)
    try:
        await page.wait_for_selector(
            '#turnstile-widget, .cf-turnstile, iframe[src*="challenges.cloudflare.com"]',
            timeout=20000,
        )
    except Exception as exc:
        logging.warning('%s Turnstile widget wait: %s', label, exc)

    async def once():
        async with ClickSolver(framework=framework, page=page, max_attempts=1, attempt_delay=2) as solver:
            await solver.solve_captcha(
                captcha_container=page,
                captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                solve_click_delay=8,
                wait_checkbox_attempts=12,
                wait_checkbox_delay=3,
                checkbox_click_attempts=3,
            )

    token = await turnstile_token(page)
    if len(token) < 20:
        try:
            await once()
            logging.info('%s Turnstile interaction finished.', label)
        except Exception as exc:
            logging.warning('%s Turnstile solve loop exited: %s', label, exc)

    for i in range(20):
        token = await turnstile_token(page)
        if len(token) > 20:
            break
        await asyncio.sleep(1)
    if len(token) < 20:
        logging.info('%s Turnstile still empty, clicking once more...', label)
        try:
            await once()
        except Exception as exc:
            logging.warning('%s Turnstile second solve exited: %s', label, exc)
        for i in range(15):
            token = await turnstile_token(page)
            if len(token) > 20:
                break
            await asyncio.sleep(1)

    logging.info('%s Turnstile token length: %s', label, len(token or ''))
    return token


def parse_captcha_code(raw):
    text = (raw or '').strip()
    if text.startswith('{') or text.startswith('['):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for key in ('code', 'result', 'text', 'data', 'answer'):
                    if data.get(key):
                        text = str(data[key])
                        break
            elif isinstance(data, list) and data:
                text = str(data[0])
        except Exception:
            pass
    digits = ''.join(ch for ch in text if ch.isdigit())
    return digits


async def main():
    global RUN_DIR
    email = os.getenv('EMAIL', '')
    password = os.getenv('PASSWORD', '')
    proxy_server = os.getenv('PROXY_SERVER')
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    captcha_api = os.getenv('CAPTCHA_API', 'https://jp--xserver--fmyy8zpzrgwf.code.run/').strip()
    if not email or not password:
        raise Exception('EMAIL and PASSWORD are required')
    logging.info('Account: 727****@gmail.com')
    logging.info('Captcha API: %s', captcha_api)
    logging.info('Run dir: %s', RUN_DIR)

    geoip_env = os.getenv('GEOIP', 'true').strip()
    if geoip_env.lower() == 'true':
        geoip_value = True
    elif geoip_env.lower() == 'false':
        geoip_value = False
    else:
        geoip_value = geoip_env

    options = {
        'headless': False,
        'humanize': True,
        'geoip': geoip_value,
        'os': 'macos',
        'screen': Screen(max_width=1280, max_height=720),
        'window': (1280, 720),
        'locale': 'ja-JP',
        'disable_coop': True,
        'i_know_what_im_doing': True,
        'config': {'forceScopeAccess': True},
        'main_world_eval': True,
        'addons': [os.path.abspath(get_addon_path())],
    }

    if proxy_server:
        parsed = urlparse(proxy_server)
        proxy_config = {
            'server': f"{parsed.scheme}://{parsed.hostname}{f':{parsed.port}' if parsed.port else ''}"
        }
        if parsed.username:
            proxy_config['username'] = parsed.username
        if parsed.password:
            proxy_config['password'] = parsed.password
        options['proxy'] = proxy_config
        logging.info('Using proxy %s', proxy_config['server'])

    logging.info('Launching Camoufox in Python...')
    async with AsyncCamoufox(**options) as browser:
        context = await browser.new_context()
        page = await context.new_page()
        framework = FrameworkType.CAMOUFOX
        result_path = os.path.join(RUN_DIR, 'RESULT.txt')

        try:
            logged_in = False
            last_login_text = ''
            for attempt in range(1, 2):
                logging.info('Navigating to login (attempt %s)...', attempt)
                await page.goto(
                    'https://secure.xserver.ne.jp/xapanel/login/xvps/',
                    wait_until='domcontentloaded',
                    timeout=60000,
                )
                await page.wait_for_selector('#memberid', timeout=30000)
                await page.locator('#memberid').fill(email)
                await page.locator('#user_password').fill(password)
                await shot(page, f'01_login_filled_{attempt}.png')

                widget = await page.evaluate('''() => ({widgets:[...document.querySelectorAll('[data-sitekey]')].map(x=>({id:x.id,sitekey:x.dataset.sitekey})),fields:[...document.querySelectorAll('input')].map(x=>({name:x.name,type:x.type})),frames:[...document.querySelectorAll('iframe')].map(x=>x.src.split('?')[0])})''')
                open(os.path.join(RUN_DIR, 'login-widget.json'), 'w').write(json.dumps(widget,ensure_ascii=False))
                token = await solve_turnstile(page, framework, 'login')
                await shot(page, f'02_login_turnstile_{attempt}.png')
                if len(token) < 20:
                    last_login_text = 'login turnstile token missing'
                    logging.error(last_login_text)
                    continue

                logging.info('Logging in...')
                submit = page.locator('#login-submit')
                if await submit.count() == 0:
                    submit = page.locator('text="ログインする"')
                await submit.click(no_wait_after=True)

                logging.info('Waiting for dashboard to load...')
                try:
                    await page.wait_for_selector('a[href^="/xapanel/xvps/server/detail?id="]', timeout=35000)
                    logged_in = True
                    break
                except Exception:
                    await shot(page, f'03_login_failed_{attempt}.png')
                    last_login_text = ' '.join((await page.inner_text('body')).split())[:900]
                    logging.error('Login did not reach dashboard. url=%s text=%s', page.url, last_login_text)
                    if 'ロック' in last_login_text:
                        raise Exception('XServer account is temporarily locked for 24 hours')
                    if '間違って' in last_login_text:
                        raise Exception('XServer rejected the account or password')
                    if 'セキュリティチェック' in last_login_text and attempt == 1:
                        logging.info('Security check rejected the token, retrying login...')
                        continue
                    raise Exception('Login did not reach dashboard')

            if not logged_in:
                raise Exception(last_login_text or 'login failed')

            await shot(page, '04_dashboard.png')
            logging.info('Dashboard reached: %s', page.url)

            try:
                modal = page.locator('#campaignModalForFreeUsers')
                if await modal.is_visible(timeout=3000):
                    logging.info('Campaign modal detected for free users, removing modal...')
                    await page.evaluate('''() => {
                        const modal = document.getElementById("campaignModalForFreeUsers");
                        if (modal) modal.remove();
                        document.querySelectorAll(".modal, .modal-backdrop, .modalIsOpen").forEach(el => el.remove());
                    }''')
            except Exception as exc:
                logging.debug('Modal check ignored: %s', exc)

            root_run_dir = RUN_DIR
            servers = await page.locator('a[href^="/xapanel/xvps/server/detail?id="]').evaluate_all('(els) => els.map(e => ({url:e.href, label:e.innerText}))')
            servers = list({x['url']:x for x in servers}.values())
            open(os.path.join(root_run_dir, 'servers.json'), 'w').write(json.dumps(servers,ensure_ascii=False,indent=2))
            open(os.path.join(root_run_dir, 'login-result.json'), 'w').write(json.dumps({'logged_in':True,'account':'727****@gmail.com','dashboard':page.url},indent=2))
            for server in servers:
                server_id = server['url'].split('id=')[-1].split('&')[0]
                RUN_DIR = os.path.join(root_run_dir, 'server-' + server_id)
                os.makedirs(RUN_DIR, mode=0o700, exist_ok=True)
                result_path = os.path.join(RUN_DIR, 'RESULT.txt')
                logging.info('Navigating server details...')
                await page.goto(server['url'], wait_until='domcontentloaded')
                logging.info('Waiting for server detail page...')
                await page.wait_for_selector('text="更新する"', timeout=30000)
                await shot(page, '05_server_detail.png')
                detail_text = ' '.join((await page.inner_text('body')).split())
                logging.info('Server detail: %s', detail_text)
                open(os.path.join(RUN_DIR, 'detail-before.txt'), 'w').write(detail_text)
                detail_url = page.url
                await page.locator('text="更新する"').click()

                logging.info('Proceeding to renewal selection...')
                await page.locator('text="引き続き無料VPSの利用を継続する"').click(no_wait_after=True)
                logging.info('Waiting for renewal page or status...')
                await page.wait_for_selector('img[src^="data:"], .newApp__suspended', timeout=30000)

                if await page.locator('.newApp__suspended').is_visible():
                    logging.info('SKIP: Renewal is not yet available (detected .newApp__suspended).')
                    logging.info("Provider window: %s", await page.locator(".newApp__suspended").inner_text())
                    await shot(page, '06_skip_renewal.png')
                    actual = await page.locator('.newApp__suspended').inner_text()
                    open(result_path, 'w', encoding='utf-8').write('NOT_ELIGIBLE\n' + actual + '\n')
                    await context.storage_state(path=os.path.join(RUN_DIR, 'session.json'))
                    await page.goto(detail_url, wait_until='domcontentloaded')
                    await page.wait_for_selector('text="更新する"', timeout=30000)
                    open(os.path.join(RUN_DIR, 'detail-after.txt'), 'w').write(' '.join((await page.inner_text('body')).split()))
                    continue

                logging.info('Retrieving captcha...')
                await shot(page, '06_captcha_page.png')
                body = await page.eval_on_selector('img[src^="data:"]', 'img => img.src')
                async with aiohttp.ClientSession() as session:
                    async with session.post(captcha_api, data=body, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        raw = await resp.text()
                        logging.info('Captcha API %s status=%s', captcha_api, resp.status)
                if not raw or 'Internal Server Error' in raw:
                    raise Exception(f'Captcha API failed: {(raw or "")[:180]}')
                code = parse_captcha_code(raw)
                logging.info('Captcha digits received: %s', len(code))
                if len(code) < 4:
                    raise Exception(f'Captcha code looks wrong: {code!r} raw={raw[:180]!r}')

                input_loc = page.locator('[placeholder="上の画像の数字を入力"]')
                await input_loc.focus()
                await input_loc.fill('')
                await input_loc.press_sequentially(code, delay=100)

                renew_token = await solve_turnstile(page, framework, 'renewal')
                await shot(page, '07_before_click.png')
                if len(renew_token) < 20:
                    logging.warning('Renewal Turnstile token missing after solver; button may stay disabled')

                await page.wait_for_selector('text="無料VPSの利用を継続する"', timeout=30000)
                button = page.locator('text="無料VPSの利用を継続する"')
                is_disabled = False
                try:
                    is_disabled = await button.is_disabled()
                except Exception:
                    pass

                if is_disabled:
                    err_msg = 'Final button is DISABLED! Renewal failed or Turnstile verification was unsuccessful.'
                    logging.error(err_msg)
                    await shot(page, '08_button_disabled.png')
                    if not debug_mode:
                        raise Exception(err_msg)
                else:
                    if debug_mode:
                        logging.info('DEBUG MODE: Final button is ENABLED. Skipping click.')
                        open(result_path, 'w', encoding='utf-8').write('DEBUG\nButton enabled, click skipped.\n')
                    else:
                        logging.info('Executing final renewal submission...')
                        await button.click(timeout=15000, no_wait_after=True)
                        await asyncio.sleep(8)
                        await shot(page, '08_after_submit.png')
                        done_text = ' '.join((await page.inner_text('body')).split())
                        logging.info('After submit snippet: %s', done_text[:800])
                        open(result_path, 'w', encoding='utf-8').write('SUBMITTED\n' + done_text[:1500] + '\n')
                        logging.info('Final renewal submitted; verifying detail')
                        await page.goto(detail_url, wait_until='domcontentloaded')
                        await page.wait_for_selector('text="更新する"', timeout=30000)
                        after_text = ' '.join((await page.inner_text('body')).split())
                        open(os.path.join(RUN_DIR, 'detail-after.txt'), 'w').write(after_text)
                        logging.info('Verified detail after: %s', after_text)

            logging.info('Done!')

        except Exception as exc:
            logging.error('Script Error: %s', exc)
            try:
                await shot(page, '99_error.png')
            except Exception:
                pass
            open(os.path.join(RUN_DIR, 'RESULT.txt'), 'w', encoding='utf-8').write(f'ERROR\n{exc}\n')
            await context.storage_state(path=os.path.join(RUN_DIR, 'session.json'))
            logging.error('Session retained on DISPLAY :99 for up to 15 minutes; no automatic resubmit. Stop file: %s/STOP', RUN_DIR)
            for _ in range(900):
                if os.path.exists(os.path.join(RUN_DIR, 'STOP')): break
                await asyncio.sleep(1)
            sys.exit(1)
        finally:
            await asyncio.sleep(2)
            await context.close()


if __name__ == '__main__':
    asyncio.run(main())
