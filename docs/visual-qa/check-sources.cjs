/* Read-only source inbox visual checks. Run while the production frontend is on port 3001. */
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'E:/codex/node_modules/playwright');

const categories = [
  { id: 1, name: '个人成长', slug: 'personal-growth', description: '持续积累的方法', sort_order: 0, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
  { id: 2, name: '嵌入式开发', slug: 'embedded', description: '硬件与软件', sort_order: 1, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
];
const topics = [
  { id: 1, category_id: 1, name: '学习方法', slug: 'learning', description: null, sort_order: 0, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
  { id: 2, category_id: 1, name: '阅读复盘', slug: 'reading', description: null, sort_order: 1, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
  { id: 3, category_id: 2, name: 'STM32', slug: 'stm32', description: null, sort_order: 0, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
];
const unscored = { relevance_score: null, relevance_passed: null, suggested_topic_id: null, relevance_method: null, relevance_reason: null, processing_status: 'unscored', processed_at: null };
const documents = [
  { ...unscored, id: 11, feed_source_id: null, provider: 'wechat_notebook', source_name: '日序', external_id: '47', title: '排序不等式及其推广', content: '排序不等式是一个经典的不等式，本身不难理解，很多读者可能在中学阶段就已经了解过它。\n本文就沿着这条线索，将这些内容串联起来介绍一下。\n基本形式\n设有两个从大到小排好序的实数列$a_1\\geq a_2\\geq \\cdots\\geq a_n$和$b_1\\geq b_2\\geq \\cdots \\geq b_n$，那么成立排序不等式\n\\begin{equation}\\sum_{i=1}^n a_i b_{n+1-i} \\leq \\sum_{i=1}^n a_i b_{\\tau(i)}\\leq \\sum_{i=1}^n a_i b_i\\end{equation}', content_hash: 'a'.repeat(64), status: 'pending', source_created_at: '2026-09-22T08:30:00+08:00', last_seen_at: '2026-09-23T05:00:00Z', source_url: null, author: null, knowledge_point_id: null, relevance_score: 0.86, relevance_passed: true, suggested_topic_id: 2, relevance_method: 'embedding', relevance_reason: '语义上与“个人成长 / 阅读复盘”最接近。', processing_status: 'scored', processed_at: '2026-09-24T02:00:00Z', created_at: '2026-09-23T05:00:00Z', updated_at: '2026-09-23T05:00:00Z' },
  { ...unscored, id: 12, feed_source_id: 2, provider: 'feed:2', source_name: '嵌入式周刊', external_id: '51', title: '调试时先缩小变量', content: '一次只改变一个变量，并记录改变前后的现象。', content_hash: 'b'.repeat(64), status: 'pending', source_created_at: '2026-09-21T20:10:00+08:00', last_seen_at: '2026-09-23T05:00:00Z', source_url: 'https://example.com/debug', author: '林默', knowledge_point_id: null, created_at: '2026-09-23T05:00:00Z', updated_at: '2026-09-23T05:00:00Z' },
  { ...unscored, id: 13, feed_source_id: 3, provider: 'feed:3', source_name: '效率研究所', external_id: '58', title: '注意力不是意志力', content: '提前移走干扰，比不断要求自己专注更有效。', content_hash: 'c'.repeat(64), status: 'pending', source_created_at: '2026-09-20T18:00:00+08:00', last_seen_at: '2026-09-23T05:00:00Z', source_url: 'https://example.com/focus', author: null, knowledge_point_id: null, relevance_reason: 'Embedding 服务暂时不可用。', processing_status: 'failed', processed_at: '2026-09-24T02:00:00Z', created_at: '2026-09-23T05:00:00Z', updated_at: '2026-09-23T05:00:00Z' },
];

async function main() {
  const outputDir = path.join(__dirname, 'sources');
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
        await context.route('**/api/v1/**', async (route) => {
          const url = new URL(route.request().url());
          if (url.pathname.endsWith('/categories')) return route.fulfill({ json: categories });
          if (url.pathname.endsWith('/topics')) return route.fulfill({ json: topics });
          if (url.pathname.endsWith('/knowledge-drafts')) return route.fulfill({ json: [] });
          if (url.pathname.endsWith('/source-documents')) return route.fulfill({ json: documents });
          return route.fulfill({ status: 404, json: { error: { message: 'Unknown fixture route' } } });
        });
        const page = await context.newPage();
        const errors = [];
        page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
        page.on('pageerror', (error) => errors.push(error.message));
        const response = await page.goto('http://localhost:3001/sources', { waitUntil: 'networkidle', timeout: 60000 });
        await page.evaluate(() => document.fonts.ready);
        await page.getByRole('button', { name: '手动整理（不调用 AI）', exact: true }).click();
        const descriptionModes = page.locator('[aria-label="知识点描述显示方式"]');
        await descriptionModes.getByRole('button', { name: '编辑', exact: true }).click();
        const editorValue = await page.getByLabel('知识点描述编辑器').inputValue();
        await descriptionModes.getByRole('button', { name: '预览', exact: true }).click();
        const name = `${device.name}-${theme}-sources`;
        await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: true, animations: 'disabled' });
        const layout = await page.evaluate((editRoundTrip) => ({
          viewportWidth: innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
          heading: document.querySelector('h1')?.textContent || null,
          selectedSource: document.querySelector('article')?.textContent?.slice(0, 80) || null,
          formulaCount: document.querySelectorAll('article .katex').length,
          sectionHeading: Array.from(document.querySelectorAll('article h2')).some((heading) => heading.textContent === '基本形式'),
          descriptionPreview: document.querySelector('article[aria-label="知识点描述预览"]')?.textContent?.includes('排序不等式') ?? false,
          descriptionFormulaCount: document.querySelectorAll('article[aria-label="知识点描述预览"] .katex').length,
          excerptHasRawMath: /[$\\]/.test(document.querySelector('[aria-label="资料列表"] li small')?.textContent || ''),
          editRoundTrip,
          relevanceScore: document.querySelector('[aria-label="相关性分析结果"] strong')?.textContent || null,
          suggestedTopic: Array.from(document.querySelectorAll('label')).find(label => label.querySelector('span')?.textContent === '主题')?.querySelector('select')?.value || null,
        }), editorValue.includes('\\begin{equation}'));
        results.push({ name, status: response?.status(), ...layout, errors });
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  await fs.writeFile(path.join(outputDir, 'results.json'), `${JSON.stringify(results, null, 2)}\n`);
  const failed = results.some((item) => item.status !== 200 || item.horizontalOverflow || item.errors.length || item.formulaCount < 4 || !item.sectionHeading || !item.descriptionPreview || item.descriptionFormulaCount < 2 || item.excerptHasRawMath || !item.editRoundTrip || item.relevanceScore !== '86%' || item.suggestedTopic !== '2');
  console.log(JSON.stringify(results, null, 2));
  if (failed) process.exitCode = 1;
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
