// Optional browser check: npm install --no-save --package-lock=false playwright
// node scripts/ui_smoke.mjs [absolute path to playwright/index.mjs]
// Requires a running local server and an installed Google Chrome browser.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.argv[2] ? pathToFileURL(process.argv[2]).href : 'playwright');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1 });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await mkdir('reports', { recursive: true });
try {
  await page.goto('http://127.0.0.1:8000');
  await page.waitForFunction(() => !document.getElementById('new-chat').disabled);
  await page.locator('#upload').setInputFiles(['examples/course-handbook.md', 'examples/project-requirements.md']);
  await page.waitForFunction(() => !document.getElementById('upload').disabled, null, { timeout: 120000 });
  assert.equal(await page.locator('.doc').count(), 2);
  await page.getByText('Inspect chunks', { exact: true }).first().click();
  await page.locator('#chunk-dialog').waitFor({ state: 'visible' });
  assert.equal(await page.locator('#chunk-dialog').evaluate(node => node.open), true);
  assert.ok(await page.locator('#chunk-content pre').count() > 0);
  await page.locator('#close-dialog').click();
  await page.locator('#tab-sources').click();
  assert.equal(await page.locator('#source-panel').isVisible(), true);
  await page.locator('#tab-agents').click();
  await page.getByText('Put a tool to work', { exact: true }).click();
  assert.match(await page.locator('#query').inputValue(), /GST/);
  const health = await page.request.get('http://127.0.0.1:8000/api/health').then(r => r.json());
  if (!health.configured) {
    await page.locator('#send').click();
    await page.waitForFunction(() => !document.getElementById('send').disabled);
    assert.match(await page.locator('#notice').textContent(), /EURI_API_KEY/);
    await page.locator('#connection').click();
    await page.waitForFunction(() => !document.getElementById('connection').disabled);
    assert.match(await page.locator('#notice').textContent(), /EURI_API_KEY/);
  }
  await page.locator('#query').fill('');
  await page.screenshot({ path: 'reports/ui-desktop.png', fullPage: true });
  for (const [width, height] of [[1024, 900], [390, 844]]) {
    await page.setViewportSize({ width, height });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `Horizontal overflow at ${width}px`);
    assert.equal(await page.locator('#send').isVisible(), true);
  }
  await page.screenshot({ path: 'reports/ui-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: real uploads, chunk inspection, source tabs, prompt selection, missing-key failures, responsive layout, no JS errors.');
  console.log('Screenshots: reports/ui-desktop.png and reports/ui-mobile.png');
} finally {
  await browser.close();
}
