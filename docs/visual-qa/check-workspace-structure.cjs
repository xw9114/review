/* Intercepted in-memory API only: never touches production, a real model or a real database. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('E:/codex/node_modules/playwright');
const base = 'http://localhost:3001';
const output = path.join(__dirname, 'workspace-structure');
const timestamp = '2026-09-25T08:00:00Z';

function fixtures() {
  const names = ['深度学习 · 测试订阅', 'ROS2 与视觉 · 测试订阅', '电控 · 测试订阅', '日序'];
  const documents = Array.from({ length: 107 }, (_, index) => {
    const id = index + 1;
    return {
      id, provider: index % 4 === 3 ? 'notebook' : 'feed:' + (index % 4 + 1),
      feed_source_id: index % 4 === 3 ? null : index % 4 + 1, source_name: names[index % 4],
      external_id: 'fixture-' + id, title: ['Adam 优化器', 'ROS2 视觉节点', '电流环 PID'][index] || '学习资料 ' + id,
      content: '## 学习笔记\n\n记录梯度 $g_t$，再核对每一步的推导。\n\n$$m_t = \\beta m_{t-1} + (1-\\beta)g_t$$',
      content_hash: String(id).padStart(64, '0'), content_origin: 'collected', content_revision: 1,
      content_chars: 110, content_warnings: [], ai_input_chars: 110, ai_input_truncated: false,
      collected_changed: false, can_supplement: index % 4 !== 3, status: 'pending',
      source_created_at: timestamp, last_seen_at: timestamp, source_url: 'https://example.com/article/' + id,
      author: id === 1 ? '测试教研员' : null, knowledge_point_id: null,
      relevance_score: null, relevance_passed: null, suggested_topic_id: null, relevance_method: null,
      relevance_reason: null, processing_status: 'unscored', processed_at: null, created_at: timestamp, updated_at: timestamp,
    };
  });
  documents.push({ ...documents[0], id: 108, title: '已入库资料', status: 'accepted', can_supplement: false, knowledge_point_id: 9 });
  const draft = {
    id: 7, revision: 1, source_document_id: 2, source_title: documents[1].title, source_name: documents[1].source_name,
    source_url: documents[1].source_url, source_content_hash: documents[1].content_hash, source_status: 'pending', topic_id: 1,
    status: 'stale', title: '已有草稿', summary: '这份草稿不应自动重新生成。', difficulty: 'beginner',
    key_points: ['保留已有内容'], quiz_items: [{ question: '如何确认？', answer: '人工审核。' }],
    model: 'qa-no-real-model', prompt_version: 'qa', generation_count: 1, generated_at: timestamp,
    reviewed_at: null, knowledge_point_id: null, created_at: timestamp, updated_at: timestamp,
  };
  return { documents, drafts: [draft], writes: [], offline: false, acceptFailure: true, generateGate: null,
    categories: [{ id: 1, name: '深度学习', slug: 'deep', sort_order: 0 }, { id: 2, name: '电控', slug: 'control', sort_order: 1 }],
    topics: [{ id: 1, category_id: 1, name: 'Optimizer', slug: 'optimizer', sort_order: 0 }] };
}

async function install(context, state) {
  await context.route('**/api/v1/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = url.pathname.replace('/api/v1', '');
    const method = request.method();
    const fail = (status, message) => route.fulfill({ status, json: { error: { message } } });
    if (method === 'OPTIONS') return route.fulfill({ status: 204 });
    if (method !== 'GET') state.writes.push({ method, endpoint, body: request.postDataJSON() });
    if (method === 'GET') {
      if (state.offline) return fail(503, '测试：资料服务暂时离线');
      if (endpoint === '/categories') return route.fulfill({ json: state.categories });
      if (endpoint === '/topics') return route.fulfill({ json: state.topics });
      if (endpoint === '/knowledge-drafts') return route.fulfill({ json: state.drafts });
      if (endpoint === '/knowledge-drafts/7') return route.fulfill({ json: state.drafts[0] });
      if (endpoint === '/source-documents') return route.fulfill({ json: state.documents.filter(item => item.status === url.searchParams.get('status')) });
      const one = endpoint.match(/^\/source-documents\/(\d+)$/);
      if (one) return route.fulfill({ json: state.documents.find(item => item.id === Number(one[1])) });
    }
    const accept = endpoint.match(/^\/source-documents\/(\d+)\/accept$/);
    if (method === 'POST' && accept) {
      if (state.acceptFailure) return fail(409, '测试：知识点名称冲突，请保留编辑后重试');
      const source = state.documents.find(item => item.id === Number(accept[1]));
      Object.assign(source, { status: 'accepted', knowledge_point_id: 10, can_supplement: false });
      return route.fulfill({ json: source });
    }
    if (method === 'POST' && endpoint.endsWith('/draft/generate')) {
      if (state.generateGate) await state.generateGate;
      return fail(503, '测试：模型暂时不可用，资料未改变');
    }
    return fail(404, 'Unexpected fixture route: ' + method + ' ' + endpoint);
  });
}

async function main() {
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Users/19890/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe' });
  const results = [];
  let lastPage;
  const check = async (name, action) => { await action(); results.push({ name, passed: true }); console.log('PASS ' + name); };
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const state = fixtures();
    await install(context, state);
    const page = await context.newPage(); lastPage = page;
    page.setDefaultTimeout(12000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const queue = page.getByRole('region', { name: '资料列表', exact: true });
    const search = page.getByRole('searchbox', { name: '搜索资料', exact: true });
    const provider = page.getByLabel('筛选来源', { exact: true });
    const detail = page.locator('#source-detail');
    const ready = () => queue.locator('li button').first().waitFor();
    const selectedTitle = () => detail.getByRole('heading', { level: 2 }).first().innerText();
    const manual = () => page.getByRole('button', { name: '手动整理（不调用 AI）', exact: false });
    const status = name => page.locator('[aria-label="资料状态筛选"]').getByRole('button', { name: new RegExp('^' + name) });
    await check('107-item queue, collapsed manual flow, no automatic writes', async () => {
      await page.goto(base + '/sources', { waitUntil: 'networkidle' }); await ready();
      assert.equal(await queue.locator('li').count(), 107);
      assert.equal(await manual().getAttribute('aria-expanded'), 'false');
      assert.equal(await page.getByLabel('知识点名称', { exact: true }).count(), 0);
      assert.deepEqual(state.writes, []);
      assert(await queue.locator('ol').evaluate(list => list.scrollHeight > list.clientHeight && list.clientHeight <= 780));
    });
    await check('search title/source/author, provider intersection, no hidden-detail actions', async () => {
      await search.fill('rOs2');
      assert((await queue.locator('li').count()) > 0);
      await provider.selectOption('feed:1');
      await queue.getByText('没有匹配的资料', { exact: true }).waitFor();
      assert.equal(await detail.locator('h2').count(), 0);
      assert.equal(await page.getByRole('button', { name: '生成 AI 草稿', exact: true }).count(), 0);
      assert.equal(new URL(page.url()).searchParams.has('source'), false);
      await page.getByRole('button', { name: '清除筛选', exact: true }).click();
      await search.fill('测试教研员');
      assert.equal(await queue.locator('li').count(), 1);
      assert.equal(await selectedTitle(), 'Adam 优化器');
      await search.fill('电流环');
      assert.equal(await queue.locator('li').count(), 1);
      assert.equal(await selectedTitle(), '电流环 PID');
      assert.deepEqual(state.writes, []);
    });
    await check('deep selection, selected row scroll, reload preserve source/status', async () => {
      await page.goto(base + '/sources?source=107&status=pending', { waitUntil: 'networkidle' });
      assert.equal(await selectedTitle(), '学习资料 107');
      assert(await queue.locator('ol').evaluate(list => {
        const item = list.querySelector('button[aria-pressed="true"]').getBoundingClientRect();
        const bounds = list.getBoundingClientRect();
        return item.top >= bounds.top - 1 && item.bottom <= bounds.bottom + 1;
      }));
      await page.reload({ waitUntil: 'networkidle' });
      assert.equal(await selectedTitle(), '学习资料 107');
      assert.equal(new URL(page.url()).searchParams.get('source'), '107');
    });
    await check('manual dirty guard on selection/filter/status/navigation/AI; collapse retains text', async () => {
      await manual().click();
      const name = page.getByLabel('知识点名称', { exact: true });
      await name.fill('我的人工理解');
      assert.equal(await page.getByRole('button', { name: '手动补充正文', exact: true }).isDisabled(), true);
      page.once('dialog', dialog => dialog.dismiss());
      await queue.locator('li button').first().click();
      assert.equal(await selectedTitle(), '学习资料 107');
      page.once('dialog', dialog => dialog.dismiss());
      await provider.selectOption('feed:1');
      assert.equal(await provider.inputValue(), '');
      page.once('dialog', dialog => dialog.dismiss());
      await search.fill('不存在的关键词');
      assert.equal(await search.inputValue(), '');
      page.once('dialog', dialog => dialog.dismiss());
      await status('已整理').click();
      assert.equal(await status('待整理').getAttribute('aria-pressed'), 'true');
      page.once('dialog', dialog => dialog.dismiss());
      await page.getByRole('link', { name: '我的知识库', exact: true }).click();
      assert.match(page.url(), /\/sources/);
      page.once('dialog', dialog => dialog.dismiss());
      await page.getByRole('button', { name: '生成 AI 草稿', exact: true }).click();
      assert.deepEqual(state.writes, []);
      await manual().click(); await manual().click();
      assert.equal(await name.inputValue(), '我的人工理解');
    });
    await check('manual accept confirmation, conflict retains edits, explicit success only', async () => {
      const submit = page.getByRole('button', { name: '直接放进知识库', exact: true });
      page.once('dialog', dialog => dialog.dismiss()); await submit.click();
      assert.deepEqual(state.writes, []);
      page.once('dialog', dialog => dialog.accept()); await submit.click();
      await page.getByRole('alert').filter({ hasText: '名称冲突' }).waitFor();
      assert.equal(await page.getByLabel('知识点名称', { exact: true }).inputValue(), '我的人工理解');
      assert.equal(await selectedTitle(), '学习资料 107');
      assert.equal(state.documents.find(item => item.id === 107).status, 'pending');
      state.acceptFailure = false;
      page.once('dialog', dialog => dialog.accept()); await submit.click();
      await page.getByText('“我的人工理解”已经进入知识库。', { exact: true }).waitFor();
      await ready();
      assert.equal(await queue.locator('li').count(), 106);
      assert.equal(state.writes.length, 2);
      assert.equal(state.writes[1].body.name, '我的人工理解');
      assert.equal(await manual().getAttribute('aria-expanded'), 'false');
      await status('已整理').click(); await ready();
      assert.equal(await queue.locator('li').count(), 2);
      assert.equal(await detail.getByRole('button', { name: '生成 AI 草稿', exact: true }).count(), 0);
      assert.equal(await detail.getByRole('link', { name: '查看知识点', exact: true }).count(), 1);
    });
    await check('failed deep-link read is not empty/success; retry retains requested source', async () => {
      state.offline = true;
      await page.goto(base + '/sources?status=accepted&source=108', { waitUntil: 'networkidle' });
      await queue.getByText('资料暂时未能加载', { exact: true }).waitFor();
      assert.equal(await status('已整理').getAttribute('aria-pressed'), 'true');
      assert.equal(await detail.locator('h2').count(), 0);
      state.offline = false;
      await queue.getByRole('button', { name: '重试读取', exact: true }).click(); await ready();
      assert.equal(await selectedTitle(), '已入库资料');
      assert.equal(new URL(page.url()).searchParams.get('source'), '108');
    });
    await check('missing topic disables new generation; in-flight request locks triage', async () => {
      await page.goto(base + '/sources?source=1', { waitUntil: 'networkidle' }); await ready();
      await detail.locator('select').first().selectOption('2');
      assert.equal(await detail.locator('select').nth(1).isDisabled(), true);
      assert.equal(await page.getByRole('button', { name: '生成 AI 草稿', exact: true }).isDisabled(), true);
      await detail.locator('select').first().selectOption('1');
      let release;
      state.generateGate = new Promise(resolve => { release = resolve; });
      await page.getByRole('button', { name: '生成 AI 草稿', exact: true }).click();
      await page.getByRole('button', { name: 'AI 正在起草…', exact: true }).waitFor();
      assert.equal(await search.isDisabled(), true);
      assert.equal(await provider.isDisabled(), true);
      assert.equal(await queue.locator('li button:not(:disabled)').count(), 0);
      assert.equal(await status('已整理').isDisabled(), true);
      release();
      await page.getByRole('alert').filter({ hasText: '模型暂时不可用' }).waitFor();
      assert.equal(await selectedTitle(), 'Adam 优化器');
      assert.equal(await page.getByRole('button', { name: '生成 AI 草稿', exact: true }).isDisabled(), false);
    });
    await check('existing stale draft opens review without new generation', async () => {
      await search.fill('ROS2 视觉节点');
      const count = state.writes.length;
      await page.getByRole('button', { name: '复核旧草稿', exact: true }).click();
      await page.waitForURL(/\/drafts\?draft=7/);
      await page.getByText('原资料已经变更', { exact: true }).waitFor();
      assert.equal(state.writes.length, count);
      assert.deepEqual(errors, []);
    });
    await context.close();
    for (const width of [1440, 768, 390, 320]) for (const theme of ['light', 'dark']) {
      await check(width + 'px ' + theme + ': six links, queue/decision layout, no overflow', async () => {
        const visual = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
        await visual.addInitScript(value => localStorage.setItem('theme', value), theme);
        const visualState = fixtures(); await install(visual, visualState);
        const p = await visual.newPage(); lastPage = p;
        const visualErrors = [];
        p.on('pageerror', error => visualErrors.push(error.message));
        p.on('console', msg => { if (msg.type() === 'error') visualErrors.push(msg.text()); });
        await p.goto(base + '/sources?source=1', { waitUntil: 'networkidle' });
        await p.getByRole('button', { name: '生成 AI 草稿', exact: true }).waitFor();
        const navigation = p.getByRole('navigation', { name: '主导航', exact: true });
        assert.equal(await navigation.getByRole('link').count(), 6);
        for (const link of await navigation.getByRole('link').all()) {
          assert.equal(await link.isVisible(), true);
          const box = await link.boundingBox();
          assert(box.x >= 0 && box.x + box.width <= width + 1);
        }
        assert.equal(await navigation.getByRole('link', { name: '资料收件箱', exact: true }).getAttribute('aria-current'), 'page');
        assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        await p.screenshot({ path: path.join(output, width + '-' + theme + '.png'), fullPage: true, animations: 'disabled' });
        if (width <= 390) {
          await p.getByRole('button', { name: '手动整理（不调用 AI）', exact: true }).click();
          await p.getByRole('article', { name: '知识点描述预览', exact: true }).locator('.katex').first().waitFor();
          assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
          await p.screenshot({ path: path.join(output, width + '-' + theme + '-manual.png'), fullPage: true });
        }
        assert.deepEqual(visualErrors, []); assert.deepEqual(visualState.writes, []);
        await visual.close();
      });
    }
  } catch (error) {
    if (lastPage && !lastPage.isClosed()) await lastPage.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    await browser.close();
    await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(results, null, 2) + '\n');
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
