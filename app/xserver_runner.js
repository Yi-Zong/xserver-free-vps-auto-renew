const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const agentScript = fs.readFileSync('/opt/xserver/app/xserver_agentbrowser.js', 'utf8');
  
  const browser = await chromium.launch({ 
    headless: true, 
    args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'] 
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    locale: 'ja-JP'
  });

  // Seed credentials into localStorage for the script to pick up
  await context.addInitScript(() => {
    localStorage.setItem('tm_memberid', 'account3');
    localStorage.setItem('tm_user_password', 'CHANGE_ME_PASSWORD');
  });

  const page = await context.newPage();
  let step = 0;
  const maxSteps = 10;

  try {
    console.log('--- 启动 XServer 自动化续期 Runner ---');
    await page.goto('https://secure.xserver.ne.jp/xapanel/login/vps/', { waitUntil: 'domcontentloaded', timeout: 60000 });

    while (step < maxSteps) {
      step++;
      const url = page.url();
      console.log(`\n[步骤 ${step}] 当前 URL: ${url}`);
      
      // Execute the agent script
      const result = await page.evaluate(agentScript).catch(e => ({ ok: false, stage: 'eval-error', error: e.message }));
      console.log(`[结果] ${JSON.stringify(result)}`);

      if (result.stage === 'no-renew-needed') {
        console.log('✅ 任务完成: 当前无需续期。');
        break;
      }
      
      if (result.stage === 'captcha-submitted') {
        console.log('⏳ 验证码已提交，等待最终结果...');
        await page.waitForTimeout(5000);
        const finalBody = await page.textContent('body').catch(() => '');
        if (finalBody.includes('完了') || finalBody.includes('受け付けました')) {
            console.log('✅ 任务完成: 续期申请成功！');
        } else {
            console.log('⚠️ 提交后页面状态不明，请检查截图。');
            await page.screenshot({ path: '/opt/xserver/xserver_final_status.png' });
        }
        break;
      }

      if (result.error && result.stage !== 'eval-error') {
        console.log(`❌ 脚本运行出错: ${result.error}`);
        await page.screenshot({ path: `/opt/xserver/xserver_error_step_${step}.png` });
        break;
      }

      // Wait for potential navigation or state change
      console.log('等待页面响应...');
      await page.waitForTimeout(8000);
      
      if (page.url() === url && step > 1 && !result.ok) {
        console.log('⚠️ 页面 URL 未变化且脚本未报告成功，可能卡住了。');
        await page.screenshot({ path: `/opt/xserver/xserver_stuck_step_${step}.png` });
        break;
      }
    }

    if (step >= maxSteps) {
      console.log('❌ 达到最大步数限制，任务中止。');
      await page.screenshot({ path: '/opt/xserver/xserver_timeout.png' });
    }

  } catch (error) {
    console.error('RUNNER_FATAL_ERROR:', error);
    await page.screenshot({ path: '/opt/xserver/xserver_fatal.png' });
  } finally {
    await browser.close();
    console.log('--- Runner 结束 ---');
  }
})();
