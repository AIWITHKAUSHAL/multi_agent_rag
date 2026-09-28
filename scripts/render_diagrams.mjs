/** Render repository-native SVGs as exact 4K, 16:9 PNG images using local Chrome. */
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(process.argv[2] ? pathToFileURL(process.argv[2]).href : 'playwright');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
  for (const name of ['02-file-call-map', '03-document-ingestion', '04-question-lifecycle']) {
    await page.goto(pathToFileURL(resolve(`docs/visuals/${name}.svg`)).href);
    await page.evaluate(() => document.fonts.ready);
    const outside = await page.locator('svg text').evaluateAll(nodes => nodes.flatMap(node => {
      const r = node.getBBox();
      return r.x < 0 || r.y < 0 || r.x + r.width > 1920 || r.y + r.height > 1080 ? [node.textContent] : [];
    }));
    assert.deepEqual(outside, [], `${name}: text outside the canvas`);
    await page.screenshot({ path: `docs/visuals/${name}.png` });
    console.log(`Rendered ${name}.png (3840 × 2160)`);
  }
} finally {
  await browser.close();
}
