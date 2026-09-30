/* Read-only feed manager visual checks. Run while the production frontend is on port 3001. */
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'E:/codex/node_modules/playwright');

const feeds = [
  { id: 1, name: '嵌入式周刊', source_type: 'rss', endpoint: 'https://example.com/embedded/feed.xml', cleaning_mode: 'auto', enabled: true, last_synced_at: '2026-09-23T06:20:00Z', last_sync_status: 'success', last_error: null, last_created: 4, last_updated: 1, last_unchanged: 18, last_failed: 0, last_cleaned: 2, created_at: '2026-09-20T00:00:00Z', updated_at: '2026-09-23T06:20:00Z' },
  { id: 2, name: 'RSSHub · 少数派', source_type: 'rsshub', endpoint: '/sspai/index', cleaning_mode: 'feed', enabled: true, last_synced_at: '2026-09-23T05:45:00Z', last_sync_status: 'partial', last_error: '1 条使用 Feed 正文回退。', last_created: 2, last_updated: 0, last_unchanged: 25, last_failed: 1, last_cleaned: 0, created_at: '2026-09-21T00:00:00Z', updated_at: '2026-09-23T05:45:00Z' },
  { id: 3, name: '暂存的研究博客', source_type: 'rss', endpoint: 'https://example.org/research.xml', cleaning_mode: 'crawl4ai', enabled: false, last_synced_at: null, last_sync_status: 'never', last_error: null, last_created: 0, last_updated: 0, last_unchanged: 0, last_failed: 0, last_cleaned: 0, created_at: '2026-09-22T00:00:00Z', updated_at: '2026-09-22T00:00:00Z' },
];

async function main() {
  const outputDir = path.join(__dirname, 'feeds');
  await fs.mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.QA_CHROMIUM_PATH || 'C:/Users/19890/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe',
  });
  const results = [];
  try {
    for (const device of [
      { name: 'desktop', viewport: { width: 1440, height: 1050 } },
      { name: 'mobile', viewport: { width: 390, height: 844 } },
    ]) {
      for (const theme of ['light', 'dark']) {
        const context = await browser.newContext({ viewport: device.viewport, colorScheme: theme });
        await context.addInitScript((value) => localStorage.setItem('theme', value), theme);
        await context.route('**/api/v1/feed-sources', (route) => route.fulfill({ json: feeds }));
        const page = await context.newPage();
        const errors = [];
        page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
        page.on('pageerror', (error) => errors.push(error.message));
        const response = await page.goto('http://localhost:3001/feeds', { waitUntil: 'networkidle', timeout: 60000 });
        await page.evaluate(() => document.fonts.ready);
        const name = `${device.name}-${theme}-feeds`;
        await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: true, animations: 'disabled' });
        const layout = await page.evaluate(() => ({
          viewportWidth: innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
          heading: document.querySelector('h1')?.textContent || null,
          sourceRows: document.querySelectorAll('ol > li').length,
        }));
        results.push({ name, status: response?.status(), ...layout, errors });
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  await fs.writeFile(path.join(outputDir, 'results.json'), `${JSON.stringify(results, null, 2)}\n`);
  const failed = results.some((item) => item.status !== 200 || item.horizontalOverflow || item.errors.length || item.sourceRows !== 3);
  console.log(JSON.stringify(results, null, 2));
  if (failed) process.exitCode = 1;
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
