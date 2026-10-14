const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.goto('http://127.0.0.1:5173/');
  await page.waitForTimeout(1500);
  await page.locator('[data-testid="role-select-admin"]').click();
  await page.locator('[data-testid="login-enter-btn"]').click();
  await page.waitForTimeout(1000);

  await page.goto('http://127.0.0.1:5173/forecast');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'scratch/screenshot_forecast.png' });

  await page.goto('http://127.0.0.1:5173/warroom');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'scratch/screenshot_warroom.png' });

  await browser.close();
  console.log('Saved screenshot_forecast.png and screenshot_warroom.png');
})();
