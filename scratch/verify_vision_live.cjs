const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function testLiveVision() {
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('1. Logging in as Administrator...');
  await page.goto('http://127.0.0.1:5173/');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1500);

  const adminRoleBtn = page.locator('[data-testid="role-select-admin"]');
  if (await adminRoleBtn.count() > 0) {
    await adminRoleBtn.click();
    await page.waitForTimeout(300);
  }
  const enterBtn = page.locator('[data-testid="login-enter-btn"]');
  if (await enterBtn.count() > 0) {
    await enterBtn.click();
    await page.waitForTimeout(1500);
  }
  console.log('Logged in. Current URL:', page.url());

  console.log('2. Navigating to http://127.0.0.1:5173/vision ...');
  await page.goto('http://127.0.0.1:5173/vision');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2500);

  // Take screenshot of Camera Wall (Matrix)
  const matrixShot = path.join(__dirname, 'screenshot_vision_matrix_live.png');
  await page.screenshot({ path: matrixShot, fullPage: false });
  console.log(`Saved Matrix screenshot to ${matrixShot}`);

  const liveText = await page.textContent('body');
  const hasLiveDetection = liveText.includes('LIVE DETECTION ACTIVE') || liveText.includes('LIVE DETECTION: ACTIVE');
  console.log('Has LIVE DETECTION banner:', hasLiveDetection);

  // Check sector filter
  console.log('3. Switching sector to Convoy & Checkpoints ...');
  const transitBtn = page.locator('button:has-text("Convoy & Checkpoints")').first();
  if (await transitBtn.isVisible()) {
    await transitBtn.click();
    await page.waitForTimeout(1500);
    const transitShot = path.join(__dirname, 'screenshot_vision_transit.png');
    await page.screenshot({ path: transitShot, fullPage: false });
    console.log(`Saved Transit Sector screenshot to ${transitShot}`);
  }

  // Switch to Neural Lab Studio
  console.log('4. Switching to Neural Lab Studio tab ...');
  const labTabBtn = page.locator('button:has-text("Neural Lab Studio")').first();
  await labTabBtn.click();
  await page.waitForTimeout(2000);

  const labShot = path.join(__dirname, 'screenshot_vision_lab_live.png');
  await page.screenshot({ path: labShot, fullPage: false });
  console.log(`Saved Neural Lab screenshot to ${labShot}`);

  // Click the prominent RUN YOLO DETECTION button
  console.log('5. Clicking RUN YOLO DETECTION button ...');
  const runYoloBtn = page.locator('#run-yolo-detection-btn').first();
  if (await runYoloBtn.isVisible()) {
    await runYoloBtn.click();
    await page.waitForTimeout(3000);
    const postInferShot = path.join(__dirname, 'screenshot_vision_lab_infer.png');
    await page.screenshot({ path: postInferShot, fullPage: false });
    console.log(`Saved Post-Inference screenshot to ${postInferShot}`);
  }

  // Check Adjudication Gate
  console.log('6. Switching to Adjudication Gate tab ...');
  const adjTabBtn = page.locator('button:has-text("Adjudication Gate")').first();
  await adjTabBtn.click();
  await page.waitForTimeout(1500);
  const adjShot = path.join(__dirname, 'screenshot_vision_adjudicate.png');
  await page.screenshot({ path: adjShot, fullPage: false });
  console.log(`Saved Adjudication screenshot to ${adjShot}`);

  await browser.close();
  console.log('All verification steps completed successfully!');
}

testLiveVision().catch((err) => {
  console.error('Test failed:', err);
  process.exit(1);
});
