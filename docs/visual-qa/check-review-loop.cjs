/* Real UI + isolated API + temporary SQLite; no production mutations or LLM calls. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'E:/codex/node_modules/playwright');
const base = 'http://localhost:3001';
const apiBase = 'http://127.0.0.1:8000/api/v1';
async function api(url, method = 'GET', body) {
  const r = await fetch(apiBase + url, { method, headers: { 'content-type': 'application/json' }, body: body && JSON.stringify(body) });
  assert.equal(r.status, 200, `${method} ${url}: ${await r.clone().text()}`);
  return r.json();
}

async function main() {
  const output = path.join(__dirname, 'review-loop');
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.QA_CHROMIUM_PATH || 'C:/Users/19890/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe' });
  const results = [];
  let lastPage;
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    lastPage = page;
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(base + '/review');
    await page.getByText('还没有可复习的题目。', { exact: false }).waitFor();
    await page.goto(base + '/sources');
    await page.getByRole('button', { name: '生成 AI 草稿', exact: true }).click();
    await page.waitForURL('**/drafts?draft=*');
    await page.getByLabel('知识点名称', { exact: true }).fill('人工审核后的 Adam');
    assert.equal((await api('/knowledge-points')).length, 0, 'Generation must not approve');
    await page.getByRole('button', { name: '展开原文，核对 AI 草稿' }).click();
    await page.locator('details .katex').first().waitFor();
    await page.getByRole('button', { name: '保存草稿', exact: true }).click();
    await page.getByText('草稿已保存，尚未进入知识库。').waitFor();
    await page.goto(base + '/sources');
    await page.getByRole('button', { name: '继续审核草稿' }).click();
    await page.waitForURL('**/drafts?draft=*');
    await page.getByLabel('摘要', { exact: true }).fill('人工核对：一阶与二阶矩估计，以及偏差修正。');
    assert.equal((await api('/knowledge-drafts'))[0].generation_count, 1);
    page.once('dialog', (dialog) => dialog.dismiss());
    await page.getByRole('link', { name: '我的知识库', exact: true }).click();
    assert.match(page.url(), /drafts/);
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: '批准入库', exact: true }).click();
    await page.getByRole('link', { name: '查看已入库知识点' }).click();
    await page.waitForURL('**/knowledge/detail?point=*');
    await page.getByRole('heading', { name: '人工审核后的 Adam', exact: true }).waitFor();
    assert.equal((await api('/knowledge-points')).length, 1);
    await page.getByRole('button', { name: '编辑内容与题目' }).click();
    await page.getByLabel('问题', { exact: true }).nth(1).fill('训练初期为什么需要偏差修正？');
    await page.getByRole('button', { name: '保存内容', exact: true }).click();
    await page.getByText('已保存。题目发生变化时，下次复习将使用新题目。').waitFor();
    await page.getByRole('link', { name: '复习这个知识点' }).click();
    await page.getByRole('button', { name: '开始这个知识点', exact: true }).click();
    await page.getByLabel('我的回答', { exact: true }).fill('梯度的指数移动平均。');
    assert.equal(await page.getByText('标准答案', { exact: true }).count(), 0);
    await page.getByRole('button', { name: '查看标准答案', exact: true }).click();
    await page.getByRole('button', { name: '基本掌握', exact: false }).waitFor();
    const sessionUrl = page.url();
    await page.reload();
    await page.getByRole('button', { name: '基本掌握', exact: false }).waitFor();
    assert.equal(await page.getByLabel('我的回答', { exact: true }).inputValue(), '梯度的指数移动平均。');
    await page.getByRole('button', { name: '基本掌握', exact: false }).click();
    await page.getByText('训练初期为什么需要偏差修正？', { exact: true }).waitFor();
    await page.getByLabel('我的回答', { exact: true }).fill('零初始化会产生偏差。');
    await page.getByRole('button', { name: '查看标准答案', exact: true }).click();
    await page.getByRole('button', { name: '有点吃力', exact: false }).click();
    await page.getByRole('heading', { name: '这一轮，已经记下了。' }).waitFor();
    const overview = await api('/reviews/overview');
    assert.equal(overview.due_count, 0);
    assert.equal(overview.reviewed_today, 2);
    assert.equal(overview.points[0].review_count, 1);
    assert.equal(overview.points[0].level, 1);
    assert.equal(overview.completed_sessions, 1);
    assert.equal(errors.length, 0, errors.join('\n'));
    results.push({ check: 'generate-save-resume-approve-edit-reveal-reload-rate', passed: true, sessionUrl });
    await page.goto(base + '/sources?source=1&status=accepted');
    await page.getByRole('link', { name: '查看知识点', exact: true }).waitFor();
    assert.equal((await api('/source-documents/1')).status, 'accepted');
    await context.close();

    const practice = await api('/reviews/sessions', 'POST', { knowledge_point_id: 1 });
    await api(`/reviews/items/${practice.items[0].id}/reveal`, 'POST', { user_answer: '这是已保存的练习回答。' });
    for (const width of [1440, 390, 320]) {
      for (const theme of ['light', 'dark']) {
        const ctx = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
        await ctx.addInitScript((value) => localStorage.setItem('theme', value), theme);
        const p = await ctx.newPage();
        lastPage = p;
        const visualErrors = [];
        p.on('pageerror', (e) => visualErrors.push(e.message));
        p.on('console', (m) => { if (m.type() === 'error') visualErrors.push(m.text()); });
        for (const [name, route] of [['dashboard', '/'], ['detail', '/knowledge/detail?point=1'], ['review', '/review'], ['drafts', '/drafts?draft=1']]) {
          const response = await p.goto(base + route, { waitUntil: 'networkidle' });
          assert.equal(response.status(), 200);
          const overflow = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth);
          assert.equal(overflow, false, `${width} ${theme} ${name} overflow`);
          assert.deepEqual((await p.getByRole('alert').allTextContents()).filter(text => text.trim()), [], `${name} error banner`);
          await p.screenshot({ path: path.join(output, `${width}-${theme}-${name}.png`), fullPage: true, animations: 'disabled' });
          results.push({ check: `${width}-${theme}-${name}`, passed: true });
        }
        assert.deepEqual(visualErrors, []);
        await ctx.close();
      }
    }
    const errorContext = await browser.newContext();
    await errorContext.route('**/reviews/overview', route => route.fulfill({ status: 503, json: { error: { message: '测试：暂时不可用' } } }));
    const errorPage = await errorContext.newPage();
    await errorPage.goto(base + '/review');
    await errorPage.getByRole('alert').filter({ hasText: '测试：暂时不可用' }).waitFor();
    await errorContext.close();
    results.push({ check: 'service-error-visible', passed: true });
  } catch (error) {
    if (lastPage && !lastPage.isClosed()) {
      console.error({ url: lastPage.url(), body: await lastPage.locator('body').innerText() });
      await lastPage.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
    }
    throw error;
  } finally { await browser.close(); }
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(results, null, 2));
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
