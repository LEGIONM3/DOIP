const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  await page.goto('http://127.0.0.1:5173/');
  await page.waitForLoadState('domcontentloaded');

  console.log('Page loaded. Checking buttons on page:');
  const buttons = await page.$$('button');
  for (let i = 0; i < buttons.length; i++) {
    const text = await buttons[i].innerText();
    console.log(`Button ${i}: "${text.replace(/\n/g, ' ')}"`);
  }
  // Wait for React to mount
  await page.waitForTimeout(1500);

  // Click the admin button (Col. A. Verma)
  const adminBtn = page.locator('[data-testid="role-select-admin"]');
  console.log('Admin button found:', await adminBtn.count());
  await adminBtn.click();
  await page.waitForTimeout(500);
  console.log('Admin button class after click:', await adminBtn.getAttribute('class'));

  // Click Enter command center
  const enterBtn = await page.locator('button', { hasText: 'Enter command center' });
  console.log('Enter button found:', await enterBtn.count());
  await enterBtn.click();
  await page.waitForTimeout(1000);

  console.log('Current URL after click:', page.url());
  const ls = await page.evaluate(() => localStorage.getItem('doip.session'));
  console.log('localStorage doip.session:', ls);

  const heading = await page.innerText('h1, header, .font-mono').catch(() => 'none');
  console.log('Page element text:', heading.slice(0, 100));

  const afterButtons = await page.$$('button');
  console.log('After login button count:', afterButtons.length);

  await browser.close();
})();
