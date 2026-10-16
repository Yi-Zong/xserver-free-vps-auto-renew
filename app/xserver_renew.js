const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const workspaceDir = __dirname;
  const agentPath = path.join(workspaceDir, 'xserver_agentbrowser.js');
  const screenshotsDir = path.join(workspaceDir, 'xserver_screenshots');
  const logsDir = path.join(workspaceDir, 'logs');
  fs.mkdirSync(screenshotsDir, { recursive: true });
  fs.mkdirSync(logsDir, { recursive: true });

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const runLogPath = path.join(logsDir, `xserver_renew_${timestamp}.log`);
  const latestLogPath = path.join(logsDir, 'xserver_renew_latest.log');
  const latestScreenshotPath = path.join(workspaceDir, 'final_result.png');

  const logLines = [];
  function log(...args) {
    const line = args.map(arg => {
      if (typeof arg === 'string') return arg;
      try { return JSON.stringify(arg); } catch { return String(arg); }
    }).join(' ');
    const entry = `[${new Date().toISOString()}] ${line}`;
    logLines.push(entry);
    console.log(entry);
  }

  function flushLogs() {
    const content = `${logLines.join('\n')}\n`;
    fs.writeFileSync(runLogPath, content);
    fs.writeFileSync(latestLogPath, content);
  }

  async function saveScreenshot(page, label, meta = {}) {
    const safeLabel = String(label || 'snapshot').replace(/[^a-zA-Z0-9_-]+/g, '_');
    const targetPath = path.join(screenshotsDir, `${timestamp}_${safeLabel}.png`);
    await page.screenshot({ path: targetPath, fullPage: true });
    fs.copyFileSync(targetPath, latestScreenshotPath);
    log('Screenshot saved', { label: safeLabel, path: targetPath, latest: latestScreenshotPath, ...meta });
    return targetPath;
  }

  function classifyFailure(res = {}, currentUrl = '') {
    if (!res || typeof res !== 'object') {
      return { category: 'unknown-failure', detail: 'no-result-object' };
    }

    const stage = res.stage || 'unknown-stage';
    const category = res.failureCategory || (
      stage.startsWith('login-') || stage === 'manual-login-needed' ? 'login-failed' :
      stage === 'no-free-vps' || stage === 'dashboard-error' ? 'vps-not-found' :
      stage === 'renew-button-missing' || stage === 'renew-link-missing' ? 'renew-button-missing' :
      stage.startsWith('turnstile-') ? 'turnstile-failed' :
      stage.startsWith('captcha-') ? 'captcha-failed' :
      stage === 'unsupported-path' ? 'unsupported-path' :
      'unknown-failure'
    );

    return {
      category,
      stage,
      currentUrl,
      error: res.error || null
    };
  }

  if (!fs.existsSync(agentPath)) {
    console.error('ERROR: xserver_agentbrowser.js not found');
    process.exit(1);
  }
  const agentScript = fs.readFileSync(agentPath, 'utf8');

  let browser;
  let page;
  let finalStatus = 'unknown';
  let finalReason = null;
  let lastResult = null;

  try {
    browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-blink-features=AutomationControlled']
    });

    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
      locale: 'ja-JP'
    });

    await context.addInitScript(() => {
      localStorage.setItem('tm_memberid', 'account3');
      localStorage.setItem('tm_user_password', 'CHANGE_ME_PASSWORD');
    });

    page = await context.newPage();
    const maxSteps = 15;
    let step = 0;

    log('Starting XServer Renew Task...', { account: 'account3' });
    await page.goto('https://secure.xserver.ne.jp/xapanel/login/vps/', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await saveScreenshot(page, 'start_login_page');

    while (step < maxSteps) {
      step++;
      const urlBefore = page.url();
      log(`Step ${step}`, { url: urlBefore });

      const res = await page.evaluate(agentScript).catch(e => ({ ok: false, stage: 'eval-error', failureCategory: 'unknown-failure', error: e.message }));
      lastResult = res;
      log('Agent result', res);

      if (!res.ok && ['login-failed', 'vps-not-found', 'renew-button-missing', 'captcha-failed', 'turnstile-failed'].includes(res.failureCategory)) {
        finalStatus = 'failed';
        finalReason = classifyFailure(res, page.url());
        await saveScreenshot(page, `failure_${finalReason.category}_${res.stage}`, { step });
        break;
      }

      if (res.stage === 'no-renew-needed') {
        finalStatus = 'success';
        finalReason = { stage: 'no-renew-needed', expireDate: res.expireDate || null };
        log('SUCCESS: No renewal needed today.');
        await saveScreenshot(page, 'success_no_renew_needed', { step, expireDate: res.expireDate || null });
        break;
      }

      if (res.stage === 'captcha-submitted') {
        log('Captcha submitted, waiting for redirect...');
        await page.waitForTimeout(15000);
        await saveScreenshot(page, 'after_captcha_submit', { step });
        const finalUrl = page.url();
        const body = await page.textContent('body').catch(() => '');
        const success = finalUrl.includes('extend/do') || body.includes('完了') || body.includes('受け付けました');
        if (success) {
          finalStatus = 'success';
          finalReason = { stage: 'renewal-completed', url: finalUrl };
          log('SUCCESS: Renewal completed successfully!');
          await saveScreenshot(page, 'success_renewal_completed', { step, url: finalUrl });
          break;
        }

        log('WARNING: Still on conf page after submission. Retrying once more...');
        const btn = await page.$('#submit_button, input[type="submit"], button[type="submit"]');
        if (btn) {
          await btn.click({ force: true, delay: 500 });
          await page.waitForTimeout(10000);
          await saveScreenshot(page, 'after_captcha_submit_retry', { step });
        } else {
          finalStatus = 'failed';
          finalReason = { category: 'captcha-failed', stage: 'captcha-submit-button-missing-post-submit', currentUrl: page.url() };
          await saveScreenshot(page, 'failure_captcha_submit_button_missing_post_submit', { step });
          break;
        }

        const retryUrl = page.url();
        const retryBody = await page.textContent('body').catch(() => '');
        const retrySuccess = retryUrl.includes('extend/do') || retryBody.includes('完了') || retryBody.includes('受け付けました');
        if (retrySuccess) {
          finalStatus = 'success';
          finalReason = { stage: 'renewal-completed-after-retry', url: retryUrl };
          log('SUCCESS: Renewal completed successfully after retry!');
          await saveScreenshot(page, 'success_renewal_completed_after_retry', { step, url: retryUrl });
          break;
        }

        finalStatus = 'failed';
        finalReason = { category: 'captcha-failed', stage: 'captcha-submit-no-success-after-retry', currentUrl: retryUrl };
        await saveScreenshot(page, 'failure_captcha_submit_no_success_after_retry', { step });
        break;
      }

      if (urlBefore.includes('xserver/index')) {
        log('Navigating to VPS management...');
        await page.goto('https://secure.xserver.ne.jp/xapanel/xvps/index', { waitUntil: 'domcontentloaded' });
        await saveScreenshot(page, 'navigated_to_xvps_index', { step });
      }

      await page.waitForTimeout(5000);
      const urlAfter = page.url();
      if (urlAfter === urlBefore && step > 2 && !res.ok) {
        finalStatus = 'failed';
        finalReason = classifyFailure(res, urlAfter);
        log('STUCK: No progress detected.', finalReason);
        await saveScreenshot(page, `failure_${finalReason.category}_stuck`, { step });
        break;
      }
    }

    if (finalStatus === 'unknown') {
      finalStatus = 'failed';
      finalReason = classifyFailure(lastResult || { stage: 'max-steps-reached', failureCategory: 'unknown-failure' }, page?.url?.() || '');
      await saveScreenshot(page, 'failure_max_steps_reached');
    }
  } catch (err) {
    finalStatus = 'failed';
    finalReason = { category: 'fatal-error', stage: 'fatal-error', error: err.message };
    log('FATAL ERROR:', err.stack || err.message || String(err));
    if (page) {
      try {
        await saveScreenshot(page, 'fatal_error');
      } catch (screenshotErr) {
        log('Failed to save fatal screenshot', screenshotErr.message || String(screenshotErr));
      }
    }
  } finally {
    log('Task finished.', { finalStatus, finalReason });
    flushLogs();
    if (browser) await browser.close();
  }
})();
