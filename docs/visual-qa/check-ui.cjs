/* Read-only visual checks. Run: node docs/visual-qa/check-ui.cjs before|after */
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'E:/codex/node_modules/playwright');

async function main() {
  const label = process.argv[2] || 'after';
  if (!/^[a-zA-Z0-9_-]+$/.test(label)) throw new Error('Use a simple artifact label.');
  const baseURL = process.env.QA_BASE_URL || 'http://localhost:3001';
  const outputDir = path.join(__dirname, label);
  await fs.mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.QA_CHROMIUM_PATH || 'C:/Users/19890/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe',
  });
  const results = [];

  try {
    for (const device of [
      { name: 'desktop', viewport: { width: 1440, height: 1000 } },
      { name: 'mobile', viewport: { width: 390, height: 844 } },
    ]) {
      for (const theme of ['light', 'dark']) {
        const context = await browser.newContext({ viewport: device.viewport, colorScheme: theme });
        await context.addInitScript((value) => localStorage.setItem('theme', value), theme);
        const blockedWrites = [];
        await context.route('**/*', async (route) => {
          const request = route.request();
          if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
            blockedWrites.push({ method: request.method(), url: request.url() });
            return route.abort('blockedbyclient');
          }
          return route.continue();
        });
        const page = await context.newPage();

        for (const entry of [{ name: 'dashboard', route: '/' }, { name: 'knowledge', route: '/knowledge' }]) {
          const errors = [];
          const failedRequests = [];
          const apiResponses = [];
          const onConsole = (message) => { if (message.type() === 'error') errors.push(message.text()); };
          const onPageError = (error) => errors.push(error.message);
          const onFailedRequest = (request) => failedRequests.push({ url: request.url(), failure: request.failure()?.errorText });
          const onResponse = (response) => { if (response.url().includes('/api/')) apiResponses.push({ url: response.url(), status: response.status() }); };
          page.on('console', onConsole);
          page.on('pageerror', onPageError);
          page.on('requestfailed', onFailedRequest);
          page.on('response', onResponse);
          const response = await page.goto(`${baseURL}${entry.route}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
          await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => undefined);
          await page.evaluate(() => document.fonts.ready);
          const name = `${device.name}-${theme}-${entry.name}`;
          await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: true, animations: 'disabled' });
          const layout = await page.evaluate(() => ({
            viewportWidth: innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
            theme: document.documentElement.dataset.theme || null,
            heading: document.querySelector('h1')?.textContent || null,
            alerts: [...document.querySelectorAll('[role="alert"]')].map((node) => node.textContent),
            bodyText: document.body.innerText.slice(0, 3000),
            visibleButtons: [...document.querySelectorAll('button')].filter((node) => node.getBoundingClientRect().width > 0).map((node) => ({
              label: node.getAttribute('aria-label') || node.innerText,
              disabled: node.disabled,
            })),
          }));
          const result = { name, status: response?.status(), ...layout, errors, failedRequests, apiResponses, blockedWrites: [...blockedWrites] };
          results.push(result);
          console.log(JSON.stringify({ name, status: result.status, horizontalOverflow: result.horizontalOverflow, errors, failedRequests, apiResponses }));
          page.off('console', onConsole);
          page.off('pageerror', onPageError);
          page.off('requestfailed', onFailedRequest);
          page.off('response', onResponse);
        }
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  await fs.writeFile(path.join(outputDir, 'results.json'), `${JSON.stringify(results, null, 2)}\n`);
  const hasFailures = results.some((result) => result.status !== 200 || result.horizontalOverflow || result.errors.length || result.failedRequests.length);
  console.log(`Visual report saved to ${outputDir}; failures: ${hasFailures}`);
  if (hasFailures) process.exitCode = 1;
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
