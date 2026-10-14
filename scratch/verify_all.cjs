const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

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
  console.log('=== STARTING PRODUCTION READINESS BROWSER VERIFICATION ===\n');
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

  // TEST 1: Login Screen & Initial Routing
  console.log('--- TEST 1: LOGIN & ROLE LANDING ROUTING ---');
  await page.goto('http://127.0.0.1:5173/');
  await page.waitForLoadState('domcontentloaded');
  // Wait for React hydration
  await page.waitForTimeout(1500);

  const adminRoleBtn = page.locator('[data-testid="role-select-admin"]');
  if (await adminRoleBtn.count() > 0) {
    await adminRoleBtn.click();
    await page.waitForTimeout(300);
  }
  const enterBtn = page.locator('[data-testid="login-enter-btn"]');
  if (await enterBtn.count() > 0) {
    await enterBtn.click();
    await page.waitForTimeout(1000);
  }

  const afterLoginUrl = page.url();
  console.log('URL after login:', afterLoginUrl);
  if (!afterLoginUrl.includes('/dashboard')) {
    console.error('FAIL: Expected /dashboard after admin login, got:', afterLoginUrl);
  } else {
    console.log('PASS: Admin landed on /dashboard');
  }

  // TEST 2: Backward & Forward Page Routing in TopBar & WorkspaceHeader
  console.log('\n--- TEST 2: BACKWARD & FORWARD PAGE ROUTING ---');
  // 1. Go to /logistics
  await page.goto('http://127.0.0.1:5173/logistics');
  await page.waitForTimeout(600);
  console.log('Step 1 URL:', page.url());

  // 2. Go to /planner
  await page.goto('http://127.0.0.1:5173/planner');
  await page.waitForTimeout(600);
  console.log('Step 2 URL:', page.url());

  // 3. Test TopBar Back button
  const topBarBackBtn = await page.$('header button[aria-label="Back"]');
  console.log('TopBar Back button exists:', !!topBarBackBtn);
  if (topBarBackBtn) {
    await topBarBackBtn.click();
    await page.waitForTimeout(600);
    console.log('URL after clicking TopBar Back button:', page.url());
  }

  // 4. Test TopBar Forward button
  const topBarFwdBtn = await page.$('header button[aria-label="Forward"]');
  console.log('TopBar Forward button exists:', !!topBarFwdBtn);
  if (topBarFwdBtn) {
    await topBarFwdBtn.click();
    await page.waitForTimeout(600);
    console.log('URL after clicking TopBar Forward button:', page.url());
  }

  // 5. Test WorkspaceHeader BACK button
  const wsHeaderBackBtn = await page.$('button[aria-label="Back to previous page"]');
  console.log('WorkspaceHeader BACK button exists:', !!wsHeaderBackBtn);
  if (wsHeaderBackBtn) {
    await wsHeaderBackBtn.click();
    await page.waitForTimeout(600);
    console.log('URL after clicking WorkspaceHeader BACK button:', page.url());
  }

  // 6. Test Keyboard Alt+ArrowLeft & Alt+ArrowRight
  await page.keyboard.press('Alt+ArrowRight');
  await page.waitForTimeout(600);
  console.log('URL after pressing Alt+ArrowRight:', page.url());

  await page.keyboard.press('Alt+ArrowLeft');
  await page.waitForTimeout(600);
  console.log('URL after pressing Alt+ArrowLeft:', page.url());

  // 7. Test Workspace Breadcrumb navigation back to workspace hub
  const wsBreadcrumbLink = await page.$('[data-testid="ws-breadcrumb-hub"]');
  console.log('Workspace Breadcrumb Hub link exists:', !!wsBreadcrumbLink);
  if (wsBreadcrumbLink) {
    const hubHref = await wsBreadcrumbLink.getAttribute('href');
    console.log('Workspace Hub target:', hubHref);
    await wsBreadcrumbLink.click();
    await page.waitForTimeout(600);
    console.log('URL after clicking Workspace Hub breadcrumb:', page.url());
  }

  // TEST 3: Deep-link search param routing from Scenario Editor to What-If
  console.log('\n--- TEST 3: DEEP-LINK ROUTING (SCENARIO EDITOR -> WHAT-IF) ---');
  await page.goto('http://127.0.0.1:5173/scenario-editor');
  await page.waitForTimeout(1000);

  const testInWhatIfBtn = await page.$('#send-to-whatif-btn');
  console.log('Test in What-If button exists:', !!testInWhatIfBtn);
  if (testInWhatIfBtn) {
    await testInWhatIfBtn.click();
    await page.waitForTimeout(1000);
    console.log('URL after clicking Test in What-If:', page.url());
    const promptText = await page.$eval('textarea', el => el.value).catch(() => 'no textarea');
    console.log('What-If prompt initialized with scenario:', promptText.includes('SC-'));
  }

  // TEST 4: Role-based Forbidden Route & In-App Backward Navigation
  console.log('\n--- TEST 4: FORBIDDEN ROUTE & IN-APP RETURN ROUTING ---');
  // Switch to operator role via TopBar
  const profileBtn = await page.$('header button[title="Operator Profile & Role Settings"]');
  if (profileBtn) {
    await profileBtn.click();
    await page.waitForTimeout(400);
    const opBtn = await page.$('button:has-text("operator")');
    if (opBtn) {
      await opBtn.click();
      await page.waitForTimeout(600);
      console.log('Switched to operator role. URL:', page.url());
    }
  }

  // Operator tries to visit /admin directly
  await page.goto('http://127.0.0.1:5173/admin');
  await page.waitForTimeout(600);
  console.log('Operator visiting /admin. Heading:', (await page.innerText('body')).slice(0, 80).replace(/\n/g, ' '));

  const returnDashBtn = await page.$('a:has-text("Return to Dashboard")');
  console.log('Return to Dashboard link present on forbidden screen:', !!returnDashBtn);
  if (returnDashBtn) {
    await returnDashBtn.click();
    await page.waitForTimeout(600);
    console.log('URL after clicking Return to Dashboard:', page.url());
  }

  // Switch back to admin role
  const profileBtn2 = await page.$('header button[title="Operator Profile & Role Settings"]');
  if (profileBtn2) {
    await profileBtn2.click();
    await page.waitForTimeout(400);
    const admBtn = await page.$('button:has-text("admin")');
    if (admBtn) {
      await admBtn.click();
      await page.waitForTimeout(600);
      console.log('Switched back to admin role.');
    }
  }

  // TEST 5: Traverse all 30 routes, verify buttons and layout
  console.log('\n--- TEST 5: VERIFY ALL 30 ROUTES, BUTTONS & LAYOUT ---');
  const routeResults = [];

  for (const route of ROUTES) {
    const targetUrl = `http://127.0.0.1:5173${route}`;
    let loaded = false;
    let buttonsCount = 0;
    let title = '';

    try {
      await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.waitForTimeout(800);
      title = await page.title();
      loaded = true;

      const buttons = await page.$$('button');
      buttonsCount = buttons.length;

      // Check if any error boundary or 404 appears unexpectedly
      const bodyText = await page.innerText('body');
      const hasError = bodyText.includes('This page didn\'t load') || bodyText.includes('Page not found');

      routeResults.push({
        route,
        loaded,
        hasError,
        buttonsCount,
        title
      });

      console.log(`Route [${route}]: OK | Buttons: ${buttonsCount} | Title: "${title}"`);
    } catch (e) {
      console.error(`Route [${route}]: FAILED -`, e.message);
      routeResults.push({ route, loaded: false, error: e.message });
    }
  }

  // Take full screenshots of key pages
  console.log('\n--- CAPTURING FULL SCREENSHOTS ---');
  await page.goto('http://127.0.0.1:5173/');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'scratch/screenshot_livemap.png' });

  await page.goto('http://127.0.0.1:5173/dashboard');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'scratch/screenshot_dashboard.png' });

  await page.goto('http://127.0.0.1:5173/vision');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: 'scratch/screenshot_vision.png' });

  await browser.close();

  console.log('\n=== SUMMARY OF VERIFICATION ===');
  console.log('Total routes tested:', routeResults.length);
  const passedRoutes = routeResults.filter(r => r.loaded && !r.hasError);
  console.log('Passed routes:', passedRoutes.length, '/', routeResults.length);
  console.log('Unhandled Page Errors:', pageErrors.length);

  fs.writeFileSync('scratch/full_verification_report.json', JSON.stringify({
    routeResults,
    pageErrors
  }, null, 2));

  console.log('\nScreenshots saved:');
  console.log(' - scratch/screenshot_livemap.png');
  console.log(' - scratch/screenshot_dashboard.png');
  console.log(' - scratch/screenshot_vision.png');
  console.log('Full report written to scratch/full_verification_report.json');
})();
