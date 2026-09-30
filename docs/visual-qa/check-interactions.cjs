/* Standalone browser QA using only intercepted in-memory API data; no database writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'E:/codex/node_modules/playwright');

const baseURL = process.env.QA_BASE_URL || 'http://localhost:3001';
const outputDir = path.join(__dirname, 'interactions');
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function until(check, message) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await check()) return;
    await sleep(100);
  }
  throw new Error(message);
}

function installFixtures(context) {
  const state = { categories: [], topics: [], 'knowledge-points': [], nextId: 1, writes: [], blockedWrites: [], offline: false };
  const setup = context.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const match = url.pathname.match(/^\/api\/v1\/(categories|topics|knowledge-points)(?:\/(\d+))?$/);
    const method = request.method();
    if (method === 'GET' && url.pathname === '/api/v1/knowledge-drafts') return route.fulfill({ json: [] });
    if (method === 'GET' && url.pathname === '/api/v1/reviews/overview') return route.fulfill({ json: { due_count: 0, reviewed_today: 0, completed_sessions: 0, active_session_id: null, points: [] } });
    if (!match) {
      if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        state.blockedWrites.push({ method, url: request.url() });
        return route.abort('blockedbyclient');
      }
      return route.continue();
    }
    const headers = {
      'access-control-allow-origin': new URL(baseURL).origin,
      'access-control-allow-methods': 'GET, POST, PATCH, DELETE, OPTIONS',
      'access-control-allow-headers': 'content-type',
    };
    const fulfill = (status, body) => route.fulfill({ status, headers, contentType: 'application/json', body: body === undefined ? '' : JSON.stringify(body) });
    if (method === 'OPTIONS') return fulfill(204);
    const [, kind, idText] = match;
    const id = Number(idText);
    if (method === 'GET') return state.offline ? fulfill(503, { detail: '测试中的临时离线' }) : fulfill(200, idText ? state[kind].find((item) => item.id === id) : state[kind]);
    const payload = method === 'DELETE' ? undefined : request.postDataJSON();
    state.writes.push({ method, kind, id: idText ? id : null, payload });
    if (method === 'POST' || method === 'PATCH') {
      const parentKey = kind === 'topics' ? 'category_id' : kind === 'knowledge-points' ? 'topic_id' : null;
      const duplicate = state[kind].some((item) => item.id !== id && item.name === payload.name && (!parentKey || item[parentKey] === payload[parentKey]));
      if (duplicate) return fulfill(409, { error: { message: '已经存在同名内容，请换一个名称' } });
      if (method === 'POST') {
        const item = { ...payload, id: state.nextId++, created_at: '2026-09-22T08:00:00Z', updated_at: '2026-09-22T08:00:00Z' };
        state[kind].push(item);
        return fulfill(201, item);
      }
      const item = state[kind].find((candidate) => candidate.id === id);
      if (!item) return fulfill(404, { detail: '内容不存在' });
      Object.assign(item, payload);
      return fulfill(200, item);
    }
    if (method === 'DELETE') {
      if (kind === 'categories') {
        const topicIds = state.topics.filter((item) => item.category_id === id).map((item) => item.id);
        state.topics = state.topics.filter((item) => item.category_id !== id);
        state['knowledge-points'] = state['knowledge-points'].filter((item) => !topicIds.includes(item.topic_id));
      }
      if (kind === 'topics') state['knowledge-points'] = state['knowledge-points'].filter((item) => item.topic_id !== id);
      state[kind] = state[kind].filter((item) => item.id !== id);
      return fulfill(204);
    }
    return fulfill(405, { detail: 'Unsupported mock method' });
  });
  return { state, setup };
}

async function testDevice(browser, device) {
  const context = await browser.newContext({ viewport: device.viewport, colorScheme: 'light' });
  const { state, setup } = installFixtures(context);
  await setup;
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const errors = [];
  const expectedErrors = [];
  const steps = [];
  let duplicateExpected = false;
  let offlineExpected = false;
  let recentPointURL = '';
  page.on('console', (event) => {
    if (event.type() !== 'error') return;
    if ((duplicateExpected && event.text().includes('409')) || (offlineExpected && event.text().includes('503'))) expectedErrors.push(event.text());
    else errors.push(event.text());
  });
  page.on('pageerror', (event) => errors.push(event.message));
  const step = async (name, action) => {
    try {
      await action();
      steps.push({ name, passed: true });
      console.log(`${device.name} PASS ${name}`);
    } catch (error) {
      steps.push({ name, passed: false, error: error.message });
      throw error;
    }
  };
  const form = () => page.locator('form');
  const submit = async (label, name, description = '') => {
    assert.equal(await form().getByLabel(`${label}名称`, { exact: true }).getAttribute('maxlength'), label === '知识点' ? '160' : '120');
    await form().getByLabel(`${label}名称`, { exact: true }).fill(name);
    if (description) await form().locator('textarea').fill(description);
    await form().getByRole('button', { name: `添加${label}`, exact: true }).click();
    await until(async () => await form().count() === 0, `${label} form did not close after submit`);
    await until(async () => await page.locator('[aria-busy="true"]').count() === 0, 'Mutation did not finish');
  };
  const pointHeading = (name) => page.getByRole('heading', { name, exact: true });

  try {
    await step('dashboard header create link opens category editor; knowledge toolbar reopens it', async () => {
      await page.goto(baseURL, { waitUntil: 'networkidle' });
      await page.getByRole('link', { name: '新建领域', exact: true }).click();
      await form().getByLabel('领域名称', { exact: true }).waitFor();
      await form().getByRole('button', { name: '取消', exact: true }).click();
      assert.equal(await form().count(), 0);
      await page.getByRole('button', { name: '新建领域', exact: true }).click();
      await form().getByLabel('领域名称', { exact: true }).waitFor();
    });
    await step('create category selects new hierarchy', async () => {
      await submit('领域', '编程', '用代码让想法落地');
      await page.getByRole('heading', { name: '编程', exact: true }).waitFor();
      assert.equal(state.categories.length, 1);
    });
    await step('create topic and two points with and without notes', async () => {
      await page.getByRole('button', { name: '新建主题', exact: true }).click();
      await submit('主题', 'Web 基础', '从浏览器开始理解互联网');
      await page.getByRole('button', { name: '记录知识点', exact: true }).click();
      await submit('知识点', '语义化 HTML', '使用合适的标签表达内容的意义');
      await pointHeading('语义化 HTML').waitFor();
      await page.getByRole('button', { name: '记录知识点', exact: true }).click();
      await submit('知识点', 'CSS 盒模型');
      await pointHeading('CSS 盒模型').waitFor();
      assert.equal(state['knowledge-points'].length, 2);
      assert(state['knowledge-points'].every((item) => item.topic_id === state.topics[0].id));
    });
    await step('search, clear, notes filter and empty result recovery', async () => {
      await page.getByRole('textbox', { name: '搜索当前主题的知识点' }).fill('html');
      assert.equal(await pointHeading('语义化 HTML').count(), 1);
      assert.equal(await pointHeading('CSS 盒模型').count(), 0);
      await page.getByRole('button', { name: '清除搜索', exact: true }).click();
      await pointHeading('CSS 盒模型').waitFor();
      await page.getByRole('button', { name: '有笔记', exact: true }).click();
      assert.equal(await pointHeading('CSS 盒模型').count(), 0);
      await page.getByRole('textbox', { name: '搜索当前主题的知识点' }).fill('not-matching');
      await page.getByRole('heading', { name: '这次没有找到匹配的知识点' }).waitFor();
      await page.getByRole('button', { name: '清除筛选', exact: true }).click();
      await pointHeading('CSS 盒模型').waitFor();
    });
    await step('edit point updates name and notes', async () => {
      await page.getByRole('button', { name: '编辑知识点“语义化 HTML”', exact: true }).click();
      await form().getByLabel('知识点名称', { exact: true }).fill('语义化 HTML 与可访问性');
      await form().locator('textarea').fill('用结构表达含义，使用地标和标签。');
      await form().getByRole('button', { name: '保存修改', exact: true }).click();
      await pointHeading('语义化 HTML 与可访问性').waitFor();
      assert.equal(state['knowledge-points'][0].description, '用结构表达含义，使用地标和标签。');
    });
    await step('duplicate API error keeps entered draft', async () => {
      await page.getByRole('button', { name: '记录知识点', exact: true }).click();
      await form().getByLabel('知识点名称', { exact: true }).fill('CSS 盒模型');
      await form().locator('textarea').fill('失败后应保留的笔记草稿');
      duplicateExpected = true;
      await form().getByRole('button', { name: '添加知识点', exact: true }).click();
      const duplicateAlert = page.getByRole('alert').filter({ hasText: '已经存在同名内容' });
      await duplicateAlert.waitFor();
      assert.match(await duplicateAlert.innerText(), /已经存在同名内容/);
      assert.equal(await form().getByLabel('知识点名称', { exact: true }).inputValue(), 'CSS 盒模型');
      assert.equal(await form().locator('textarea').inputValue(), '失败后应保留的笔记草稿');
      await form().getByRole('button', { name: '取消', exact: true }).click();
      await page.getByRole('button', { name: '关闭错误提示' }).click();
      duplicateExpected = false;
      assert.equal(state['knowledge-points'].length, 2);
    });
    await step('cancel delete preserves item; accept delete removes only selected item', async () => {
      const beforeDeleteWrites = state.writes.filter((item) => item.method === 'DELETE').length;
      page.once('dialog', (dialog) => dialog.dismiss());
      await page.getByRole('button', { name: '删除知识点“CSS 盒模型”', exact: true }).click();
      assert.equal(state.writes.filter((item) => item.method === 'DELETE').length, beforeDeleteWrites);
      assert.equal(await pointHeading('CSS 盒模型').count(), 1);
      page.once('dialog', (dialog) => dialog.accept());
      await page.getByRole('button', { name: '删除知识点“CSS 盒模型”', exact: true }).click();
      await until(async () => await pointHeading('CSS 盒模型').count() === 0, 'Deleted point remained visible');
      assert.equal(state['knowledge-points'].length, 1);
      assert.equal(await pointHeading('语义化 HTML 与可访问性').count(), 1);
    });
    await step('new topic and category selection isolate knowledge points', async () => {
      await page.getByRole('button', { name: '新建主题', exact: true }).click();
      await submit('主题', 'JavaScript');
      await page.getByRole('button', { name: '记录知识点', exact: true }).click();
      await submit('知识点', '闭包', '函数记住定义时的作用域');
      await pointHeading('闭包').waitFor();
      assert.equal(await pointHeading('语义化 HTML 与可访问性').count(), 0);
      await page.getByRole('button', { name: /^Web 基础/ }).click();
      await pointHeading('语义化 HTML 与可访问性').waitFor();
      assert.equal(await pointHeading('闭包').count(), 0);
      await page.getByRole('button', { name: '新建领域', exact: true }).click();
      await submit('领域', '摄影', '留意生活里的光');
      await page.getByRole('heading', { name: '摄影', exact: true }).waitFor();
      assert.equal(await pointHeading('语义化 HTML 与可访问性').count(), 0);
      await page.getByRole('button', { name: '新建主题', exact: true }).click();
      await submit('主题', '构图');
      await page.getByRole('button', { name: '记录知识点', exact: true }).click();
      await submit('知识点', '三分法', '让主体沿九宫格交点分布');
      await pointHeading('三分法').waitFor();
      await page.getByRole('complementary', { name: '知识领域' }).getByRole('button', { name: /^编程/ }).click();
      await pointHeading('语义化 HTML 与可访问性').waitFor();
      assert.equal(await pointHeading('三分法').count(), 0);
    });
    await step('theme toggles and persists reload without hydration errors', async () => {
      await page.getByRole('button', { name: '切换到深色模式' }).click();
      await until(() => page.evaluate(() => document.documentElement.dataset.theme === 'dark'), 'Dark theme not applied');
      assert.equal(await page.evaluate(() => localStorage.getItem('theme')), 'dark');
      await page.reload({ waitUntil: 'networkidle' });
      await page.getByRole('button', { name: '切换到浅色模式' }).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), 'dark');
      await page.getByRole('button', { name: '切换到浅色模式' }).click();
    });
    await step('seed sample fixture hierarchy and capture populated states', async () => {
      state.categories = [
        { id: 101, name: '设计与创造', description: '在日常里收集灵感，把想法变成作品。' },
        { id: 102, name: '代码与逻辑', description: '理解工具，也理解问题本身。' },
        { id: 103, name: '生活的练习', description: '保持对世界的好奇。' },
      ];
      state.topics = [
        { id: 201, category_id: 101, name: '视觉设计', description: '让信息有秩序，也让表达有温度。' },
        { id: 202, category_id: 101, name: '字体与排版', description: '' },
        { id: 203, category_id: 102, name: 'Web 基础', description: '' },
      ];
      state['knowledge-points'] = [
        { id: 301, topic_id: 201, name: '留白，是留给注意力的空间', description: '当每个元素都想被看见，反而没有重点。用留白分组，让内容能够呼吸。' },
        { id: 302, topic_id: 201, name: '建立清晰的视觉层级', description: '先确定最重要的信息，再通过字号、字重和位置建立阅读顺序。' },
        { id: 303, topic_id: 201, name: '色彩的 60 / 30 / 10 原则', description: '' },
        { id: 304, topic_id: 202, name: '行长影响阅读节奏', description: '让每一行保持容易扫读的长度。' },
      ].map((item, index) => ({ ...item, created_at: '2026-09-22T08:00:00Z', updated_at: `2026-09-22T08:0${index}:00Z` }));
      await page.goto(`${baseURL}/knowledge`, { waitUntil: 'networkidle' });
      await pointHeading('留白，是留给注意力的空间').waitFor();
      await page.screenshot({ path: path.join(outputDir, `${device.name}-light-knowledge-fixture.png`), fullPage: true, animations: 'disabled' });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.getByRole('button', { name: '切换到深色模式' }).click();
      await page.screenshot({ path: path.join(outputDir, `${device.name}-dark-knowledge-fixture.png`), fullPage: true, animations: 'disabled' });
      await page.getByRole('link', { name: '今日概览', exact: true }).click();
      await page.getByRole('heading', { name: '设计与创造', exact: true }).waitFor();
      await page.screenshot({ path: path.join(outputDir, `${device.name}-dark-dashboard-fixture.png`), fullPage: true, animations: 'disabled' });
      await page.getByRole('button', { name: '切换到浅色模式' }).click();
      await page.screenshot({ path: path.join(outputDir, `${device.name}-light-dashboard-fixture.png`), fullPage: true, animations: 'disabled' });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      assert.equal(state.blockedWrites.length, 0);
      assert.deepEqual(errors, []);
    });
    await step('recent point link selects second topic and focuses requested knowledge point', async () => {
      recentPointURL = await page.getByRole('link', { name: /行长影响阅读节奏/ }).getAttribute('href');
      await page.getByRole('link', { name: /行长影响阅读节奏/ }).click();
      await pointHeading('行长影响阅读节奏').waitFor();
      assert.equal(await page.getByRole('button', { name: /^字体与排版/ }).getAttribute('aria-pressed'), 'true');
      assert.equal(await pointHeading('留白，是留给注意力的空间').count(), 0);
      await until(() => page.evaluate(() => document.activeElement?.id === 'knowledge-point-304'), 'Recent point did not receive focus');
      await page.getByRole('link', { name: '搜索知识库', exact: true }).click();
      await until(() => page.evaluate(() => document.activeElement?.id === 'knowledge-search'), 'Search shortcut did not focus field');
      assert.equal(await page.getByRole('button', { name: /^字体与排版/ }).getAttribute('aria-pressed'), 'true');
    });
    await step('initial knowledge API 503 shows unavailable state then retry restores data', async () => {
      state.offline = true;
      offlineExpected = true;
      await page.goto(`${baseURL}${recentPointURL}`, { waitUntil: 'networkidle' });
      await page.getByRole('heading', { name: '知识库暂时没连上', exact: true }).waitFor();
      assert.equal(await page.getByRole('button', { name: '新建领域', exact: true }).isDisabled(), true);
      assert.equal(await page.getByRole('heading', { name: '从一个感兴趣的领域开始', exact: true }).count(), 0);
      state.offline = false;
      await page.getByRole('button', { name: '重新连接', exact: true }).click();
      await pointHeading('行长影响阅读节奏').waitFor();
      assert.equal(await page.getByRole('button', { name: '新建领域', exact: true }).isDisabled(), false);
      offlineExpected = false;
    });
    await step('dashboard API 503 reconnect restores populated statistics', async () => {
      state.offline = true;
      offlineExpected = true;
      await page.goto(baseURL, { waitUntil: 'networkidle' });
      await page.getByRole('alert').filter({ hasText: 'API 尚未连接' }).waitFor();
      state.offline = false;
      await page.getByRole('button', { name: '重新连接', exact: true }).click();
      await page.getByRole('heading', { name: '设计与创造', exact: true }).waitFor();
      assert.equal(await page.getByRole('alert').filter({ hasText: 'API 尚未连接' }).count(), 0);
      offlineExpected = false;
      assert.deepEqual(errors, []);
      assert.equal(state.blockedWrites.length, 0);
    });
  } catch (error) {
    console.error(`${device.name} FAIL ${error.stack}`);
    await page.screenshot({ path: path.join(outputDir, `${device.name}-failure-fixture.png`), fullPage: true }).catch(() => {});
  } finally {
    await context.close();
  }
  return { device: device.name, steps, errors, expectedErrors, interceptedWrites: state.writes, blockedWrites: state.blockedWrites };
}

async function testTablet(browser) {
  const context = await browser.newContext({ viewport: { width: 768, height: 1024 }, colorScheme: 'light' });
  const { setup, state } = installFixtures(context);
  await setup;
  const page = await context.newPage();
  const errors = [];
  const steps = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  try {
    await page.goto(baseURL, { waitUntil: 'networkidle' });
    for (const name of ['今日概览', '我的知识库']) {
      const link = page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name, exact: true });
      assert.equal(await link.isVisible(), true);
      const box = await link.boundingBox();
      assert(box && box.x >= 0 && box.x + box.width <= 768);
    }
    await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '我的知识库', exact: true }).click();
    await page.getByRole('heading', { name: '从一个感兴趣的领域开始', exact: true }).waitFor();
    assert.equal(await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '我的知识库', exact: true }).getAttribute('aria-current'), 'page');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({ path: path.join(outputDir, 'tablet-light-knowledge-empty-fixture.png'), fullPage: true, animations: 'disabled' });
    assert.deepEqual(errors, []);
    assert.equal(state.writes.length, 0);
    steps.push({ name: '768px main navigation remains visible, usable and in viewport', passed: true });
    console.log('tablet PASS 768px main navigation remains visible, usable and in viewport');
  } catch (error) {
    steps.push({ name: '768px main navigation remains visible, usable and in viewport', passed: false, error: error.message });
    console.error(`tablet FAIL ${error.message}`);
  } finally { await context.close(); }
  return { device: 'tablet', steps, errors, blockedWrites: state.blockedWrites };
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.QA_CHROMIUM_PATH || 'C:/Users/19890/AppData/Local/ms-playwright/chromium-1217/chrome-win64/chrome.exe' });
  const results = [];
  try {
    for (const device of [
      { name: 'desktop', viewport: { width: 1440, height: 1000 } },
      { name: 'mobile', viewport: { width: 390, height: 844 } },
    ]) results.push(await testDevice(browser, device));
    results.push(await testTablet(browser));
  } finally { await browser.close(); }
  await fs.writeFile(path.join(outputDir, 'results.json'), `${JSON.stringify(results, null, 2)}\n`);
  if (results.some((result) => result.steps.some((step) => !step.passed) || result.errors.length)) process.exitCode = 1;
  console.log(`Interaction report: ${path.join(outputDir, 'results.json')}`);
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
