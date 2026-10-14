const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge' });
  const page = await browser.newPage();
  
  page.on('pageerror', err => console.log('FORECAST PAGE ERROR:', err.stack || err.message));
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('FORECAST CONSOLE ERROR:', msg.text());
  });

  await page.goto('http://127.0.0.1:5173/');
  await page.waitForTimeout(1500);
  await page.locator('[data-testid="role-select-admin"]').click();
  await page.locator('[data-testid="login-enter-btn"]').click();
  await page.waitForTimeout(1000);

  console.log('\n--- NAVIGATING DIRECTLY TO /forecast ---');
  await page.goto('http://127.0.0.1:5173/forecast');
  await page.waitForTimeout(2000);
  await browser.close();
})();
