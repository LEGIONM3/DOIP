const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge' });
  const page = await browser.newPage();
  
  page.on('pageerror', err => console.log('PAGE ERROR CAUGHT:', err.stack || err.message));
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
  });

  await page.goto('http://127.0.0.1:5173/');
  await page.waitForTimeout(1500);
  await page.locator('[data-testid="role-select-admin"]').click();
  await page.locator('[data-testid="login-enter-btn"]').click();
  await page.waitForTimeout(1000);

  console.log('\n--- CHECKING FORECAST ---');
  await page.goto('http://127.0.0.1:5173/forecast');
  await page.waitForTimeout(1000);
  const forecastText = await page.innerText('body');
  console.log('Forecast body excerpt:\n', forecastText.slice(0, 500));
  console.log('Includes "This page didn\'t load"?', forecastText.includes("This page didn't load"));

  console.log('\n--- CHECKING WARROOM ---');
  await page.goto('http://127.0.0.1:5173/warroom');
  await page.waitForTimeout(1000);
  const warroomText = await page.innerText('body');
  console.log('Warroom body excerpt:\n', warroomText.slice(0, 500));
  console.log('Includes "This page didn\'t load"?', warroomText.includes("This page didn't load"));

  await browser.close();
})();
