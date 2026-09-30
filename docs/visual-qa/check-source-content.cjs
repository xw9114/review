/* Source-content workflow against SOURCE_SUPPLEMENT_QA=1, isolated SQLite + fake crawler/LLM. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('E:/codex/node_modules/playwright');
const base = 'http://localhost:3001';
const apiBase = 'http://127.0.0.1:8000/api/v1';
async function api(url, method = 'GET', body) {
  const r = await fetch(apiBase + url, { method, headers: { 'content-type': 'application/json' }, body: body && JSON.stringify(body) });
  assert.equal(r.status, 200, `${method} ${url}: ${await r.clone().text()}`);
  return r.json();
}

async function main() {
  const output = path.join(__dirname, 'source-content');
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/19890/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe' });
  const results = [];
  let lastPage;
  try {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await ctx.newPage(); lastPage = page;
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const source = await api('/source-documents/1');
    const draft = await api('/source-documents/1/draft/generate', 'POST', { topic_id: 1 });
    await page.goto(base + '/sources?source=1');
    await page.getByText('疑似摘要：', { exact: false }).waitFor();
    await page.getByRole('button', { name: '抓取正文预览', exact: true }).click();
    await page.getByText('候选正文 · 尚未应用', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: '继续审核草稿' }).isDisabled(), true);
    assert.deepEqual(await api('/source-documents/1'), source);
    await page.getByLabel('候选正文预览').locator('.katex').first().waitFor();
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '取消补充' }).click();
    assert.deepEqual(await api('/source-documents/1'), source);
    await page.getByRole('button', { name: '手动补充正文' }).click();
    const manual = '## 人工补充\n\n梯度的一阶矩 $m_t$ 用于更新方向。\n\n$$m_t = \\beta m_{t-1} + (1-\\beta)g_t$$\n\n需要偏差修正。';
    await page.getByLabel('候选正文编辑器').fill(manual);
    page.once('dialog', dialog => dialog.dismiss());
    await page.getByRole('link', { name: '我的知识库', exact: true }).click();
    assert.match(page.url(), /sources/);
    await page.getByRole('button', { name: '预览排版' }).click();
    await page.getByLabel('候选正文预览').locator('.katex').first().waitFor();
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '确认应用正文' }).click();
    await page.getByText('已确认补充正文', { exact: true }).waitFor();
    assert.equal((await api('/source-documents/1')).content, manual);
    assert.equal((await api('/knowledge-drafts/1')).status, 'stale');
    assert.equal((await api('/knowledge-drafts/1')).summary, draft.summary);
    await api('/feed-sources/1/sync', 'POST');
    assert.equal((await api('/source-documents/1')).content, manual);
    await page.getByRole('button', { name: '复核旧草稿' }).click();
    await page.getByText('原资料已经变更', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: '批准入库', exact: true }).count(), 0);
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '重新生成', exact: true }).click();
    await page.getByText('已重新生成，请再次核对原文和答案。').waitFor();
    assert.equal((await api('/knowledge-drafts/1')).generation_count, 2);
    assert.equal((await api('/knowledge-points')).length, 0);
    await page.goto(base + '/sources?source=1');
    await page.getByRole('button', { name: '查看订阅内容' }).click();
    await page.getByRole('button', { name: '恢复为订阅内容' }).waitFor();
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '恢复为订阅内容' }).click();
    await page.getByText('采集正文', { exact: true }).waitFor();
    assert.equal((await api('/source-documents/1')).content, source.content);
    results.push({ check: 'preview-cancel-manual-apply-sync-protect-stale-regenerate-restore', passed: true });

    await page.getByRole('button', { name: '手动补充正文' }).click();
    await page.getByLabel('候选正文编辑器').fill('我的候选正文：保留这段文字。');
    const current = await api('/source-documents/1');
    await api('/source-documents/1/content', 'PATCH', { content: '另一页更新的内容', expected_revision: current.content_revision });
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '确认应用正文' }).click();
    await page.getByRole('alert').filter({ hasText: '资料已在其他页面更新' }).waitFor();
    assert.equal(await page.getByLabel('候选正文编辑器').inputValue(), '我的候选正文：保留这段文字。');
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '取消补充' }).click();
    await page.reload();
    await ctx.route('**/content-preview', route => route.fulfill({ status: 502, json: { error: { message: '测试：原网页暂时不可用，请手动粘贴。' } } }));
    await page.getByRole('button', { name: '抓取正文预览' }).click();
    await page.getByRole('alert').filter({ hasText: '测试：原网页暂时不可用' }).waitFor();
    await page.getByRole('button', { name: '手动补充正文' }).click();
    await page.getByLabel('候选正文编辑器').fill('文'.repeat(13000));
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '确认应用正文' }).click();
    await page.getByText('AI 本次只读取前', { exact: false }).waitFor();
    assert.equal((await api('/source-documents/1')).content_chars, 13000);
    assert.deepEqual(errors, []);
    results.push({ check: 'conflict-preserves-input-crawl-failure-manual-fallback-budget-warning', passed: true });
    await ctx.close();

    for (const width of [1440, 390, 320]) {
      for (const theme of ['light', 'dark']) {
        const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
        await context.addInitScript(theme => localStorage.setItem('theme', theme), theme);
        const p = await context.newPage(); lastPage = p;
        const visualErrors = [];
        p.on('pageerror', error => visualErrors.push(error.message));
        p.on('console', m => { if (m.type() === 'error') visualErrors.push(m.text()); });
        await p.goto(base + '/sources?source=1', { waitUntil: 'networkidle' });
        await p.getByRole('button', { name: '抓取正文预览' }).click();
        await p.getByText('候选正文 · 尚未应用', { exact: true }).waitFor();
        await p.getByLabel('候选正文预览').locator('.katex').first().waitFor();
        assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${width}-${theme} overflow`);
        assert.deepEqual((await p.getByRole('alert').allTextContents()).filter(text => text.trim()), []);
        await p.screenshot({ path: path.join(output, `${width}-${theme}-preview.png`), fullPage: true });
        await p.getByRole('button', { name: '编辑正文' }).click();
        assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        await p.screenshot({ path: path.join(output, `${width}-${theme}-editor.png`), fullPage: true });
        assert.deepEqual(visualErrors, []);
        results.push({ check: `${width}-${theme}-preview-editor`, passed: true });
        await context.close();
      }
    }
  } catch (error) {
    if (lastPage && !lastPage.isClosed()) await lastPage.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
    throw error;
  } finally { await browser.close(); }
  await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(results));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
