const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage({ locale: 'ja-JP' });
  try {
    await page.goto('https://secure.xserver.ne.jp/xapanel/login/vps/', { waitUntil: 'domcontentloaded' });
    await page.fill('input[name="memberid"]', 'account3');
    await page.fill('input[name="user_password"]', 'CHANGE_ME_PASSWORD');
    await page.click('input[type="submit"]');
    await page.waitForTimeout(10000);
    await page.goto('https://secure.xserver.ne.jp/xapanel/xvps/index', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000);
    const text = await page.evaluate(() => document.body.innerText);
    console.log('BODY:', text.replace(/\s+/g, ' ').slice(0, 1000));
  } finally {
    await browser.close();
  }
})();
