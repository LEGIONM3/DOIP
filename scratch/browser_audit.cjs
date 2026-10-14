const { chromium } = require('playwright');
const fs = require('fs');

const ROUTES = [
  '/',
  '/dashboard',
  '/run',
  '/planner',
  '/federation',
  '/theaters',
  '/campaigns',
  '/futures',
  '/datalake',
  '/doctrine',
  '/replay',
  '/sitrep',
  '/forecast',
  '/graph',
  '/whatif',
  '/vision',
  '/logistics',
  '/personnel',
  '/analytics',
  '/advisor',
  '/warroom',
  '/agents',
  '/memory',
  '/analytics-center',
  '/workflows',
  '/models',
  '/observability',
  '/model-lab',
  '/scenario-editor',
  '/admin'
];

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push({ url: page.url(), text: msg.text() });
    }
  });

  page.on('pageerror', err => {
    pageErrors.push({ url: page.url(), error: err.message });
  });

  console.log('--- STEP 1: INITIAL VISIT & LOGIN SCREEN ---');
  await page.goto('http://127.0.0.1:5173/');
  await page.waitForLoadState('networkidle');

  // Verify LoginScreen
  const enterBtn = await page.$('button:has-text("Enter command center")');
  console.log('Login button visible:', !!enterBtn);
  if (enterBtn) {
    // Select admin role
    const adminBtn = await page.$('button:has-text("ADMIN")');
    if (adminBtn) await adminBtn.click();
    await enterBtn.click();
    await page.waitForTimeout(1000);
  }

  console.log('--- STEP 2: VERIFY ALL ROUTES & BUTTONS ---');
  const routeAudit = [];

  for (const route of ROUTES) {
    const targetUrl = `http://127.0.0.1:5173${route}`;
    let loaded = true;
    let title = '';
    let buttonsCount = 0;
    let nonClickableButtons = [];

    try {
      await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 8000 });
      title = await page.title();
      
      // Get all buttons on the page
      const buttons = await page.$$('button');
      buttonsCount = buttons.length;

      for (let i = 0; i < buttons.length; i++) {
        const btn = buttons[i];
        try {
          const isVisible = await btn.isVisible();
          const isEnabled = await btn.isEnabled();
          const box = await btn.boundingBox();
          const text = (await btn.innerText()).trim() || (await btn.getAttribute('title')) || (await btn.getAttribute('aria-label')) || `btn-${i}`;
          
          if (!isVisible) {
            // Check if hidden by design or misaligned
            nonClickableButtons.push({ index: i, text, reason: 'NOT_VISIBLE' });
          } else if (box && (box.width === 0 || box.height === 0)) {
            nonClickableButtons.push({ index: i, text, reason: 'ZERO_SIZE' });
          }
        } catch (e) {
          // Stale element or other
        }
      }

    } catch (e) {
      loaded = false;
      console.log(`Failed loading ${route}:`, e.message);
    }

    routeAudit.push({
      route,
      loaded,
      title,
      buttonsCount,
      nonClickableButtons: nonClickableButtons.slice(0, 5) // top 5
    });
    console.log(`Route ${route}: loaded=${loaded}, buttons=${buttonsCount}, non-clickable/invisible=${nonClickableButtons.length}`);
  }

  console.log('--- STEP 3: BACKWARD NAVIGATION TEST ---');
  // Navigate through 3 routes and test browser goBack and in-app backward navigation
  await page.goto('http://127.0.0.1:5173/dashboard');
  await page.waitForTimeout(500);
  await page.goto('http://127.0.0.1:5173/planner');
  await page.waitForTimeout(500);
  await page.goto('http://127.0.0.1:5173/whatif');
  await page.waitForTimeout(500);

  // Check if there is an in-app Back button in TopBar or WorkspaceHeader
  const inAppBackBtn = await page.$('button[title*="Back"], button:has-text("Back"), a:has-text("Back")');
  console.log('In-app Back navigation element present:', !!inAppBackBtn);

  // Test browser goBack
  await page.goBack();
  const back1Url = page.url();
  console.log('After page.goBack(), URL is:', back1Url);

  await page.goBack();
  const back2Url = page.url();
  console.log('After second page.goBack(), URL is:', back2Url);

  await page.goForward();
  const forward1Url = page.url();
  console.log('After page.goForward(), URL is:', forward1Url);

  console.log('\n--- CONSOLE ERRORS SUMMARY ---');
  console.log('Console errors count:', consoleErrors.length);
  consoleErrors.slice(0, 15).forEach(e => console.log(`  [${e.url}] ${e.text}`));

  console.log('\n--- PAGE ERRORS SUMMARY ---');
  console.log('Page errors count:', pageErrors.length);
  pageErrors.forEach(e => console.log(`  [${e.url}] ${e.error}`));

  await browser.close();

  fs.writeFileSync('scratch/audit_report.json', JSON.stringify({
    routeAudit,
    consoleErrors,
    pageErrors,
    inAppBackBtn: !!inAppBackBtn
  }, null, 2));

  console.log('\nAudit completed and saved to scratch/audit_report.json');
})();
