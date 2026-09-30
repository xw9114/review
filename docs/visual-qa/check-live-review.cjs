/* Read-only production browser smoke via localhost SSH forwards; blocks every write. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'E:/codex/node_modules/playwright');
const base = 'http://127.0.0.1:13001';
const backend = 'http://127.0.0.1:18000';

async function main() {
  const out = path.join(__dirname, 'live-review');
  await fs.mkdir(out, { recursive: true });
  const draftsResponse = await fetch(backend + '/api/v1/knowledge-drafts');
  assert.ok(draftsResponse.ok);
  const drafts = await draftsResponse.json();
  const pointsResponse = await fetch(backend + '/api/v1/knowledge-points');
  assert.ok(pointsResponse.ok);
  const points = await pointsResponse.json();
  assert.ok(drafts.length && points.length);
  const sourceResponse = await fetch(backend + '/api/v1/source-documents/' + drafts[0].source_document_id);
  assert.ok(sourceResponse.ok);
  const source = await sourceResponse.json();
  const browser = await chromium.launch({ headless: true, executablePath: process.env.QA_CHROMIUM_PATH || 'C:/Users/19890/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe' });
  const results = [];
  try {
    for (const [width, theme] of [[1440, 'light'], [320, 'dark']]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
      await context.addInitScript(theme => localStorage.setItem('theme', theme), theme);
      const blockedWrites = [];
      await context.route('**/*', async route => {
        const request = route.request();
        if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
          blockedWrites.push(request.method() + ' ' + request.url());
          return route.abort();
        }
        const url = new URL(request.url());
        if (url.pathname.startsWith('/api/v1/')) {
          const response = await route.fetch({ url: backend + url.pathname + url.search });
          return route.fulfill({ response });
        }
        return route.continue();
      });
      const page = await context.newPage();
      const errors = [];
      page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
      page.on('pageerror', error => errors.push(error.message));
      const routes = [['dashboard', '/'], ['source', `/sources?status=${source.status}&source=${source.id}`], ['draft', `/drafts?draft=${drafts[0].id}`], ['detail', `/knowledge/detail?point=${points[0].id}`], ['review', '/review']];
      for (const [name, route] of routes) {
        const response = await page.goto(base + route, { waitUntil: 'networkidle' });
        assert.equal(response.status(), 200);
        if (name === 'source') {
          await page.getByRole('heading', { name: source.title, exact: true }).waitFor();
          await page.getByRole('region', { name: '正文完整性' }).waitFor();
          assert.equal(await page.getByRole('button', { name: '抓取正文预览' }).count(), source.can_supplement ? 1 : 0);
        }
        if (name === 'draft') {
          await page.getByRole('button', { name: '展开原文，核对 AI 草稿' }).click();
          await page.locator('details').first().waitFor();
          if (drafts[0].status === 'approved') {
            await page.getByRole('link', { name: '查看已入库知识点' }).waitFor();
            assert.equal(await page.getByRole('button', { name: '批准入库', exact: true }).count(), 0);
          } else if (drafts[0].source_status === 'pending' && drafts[0].status !== 'stale') {
            assert.ok(await page.getByRole('button', { name: '批准入库', exact: true }).isEnabled());
          }
        }
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        assert.equal(overflow, false, `${name} ${width}: overflow`);
        assert.deepEqual((await page.getByRole('alert').allTextContents()).filter(text => text.trim()), []);
        await page.screenshot({ path: path.join(out, `${width}-${theme}-${name}.png`), fullPage: true, animations: 'disabled' });
        results.push({ name, width, theme, status: response.status(), horizontalOverflow: overflow });
      }
      assert.deepEqual(errors, []);
      assert.deepEqual(blockedWrites, []);
      await context.close();
    }
    const after = await (await fetch(backend + '/api/v1/knowledge-drafts')).json();
    assert.equal(after[0].status, drafts[0].status, 'Read-only smoke must not approve');
    await fs.writeFile(path.join(out, 'results.json'), JSON.stringify({ readOnly: true, draftId: drafts[0].id, results }, null, 2) + '\n');
    console.log(JSON.stringify({ readOnly: true, draftId: drafts[0].id, passed: results.length }));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
