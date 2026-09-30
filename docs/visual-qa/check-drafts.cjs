/* Read-only AI draft review visual checks. Run while the production frontend is on port 3001. */
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'E:/codex/node_modules/playwright');

const categories = [
  { id: 1, name: '深度学习', slug: 'deep-learning', description: '模型训练', sort_order: 0, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
  { id: 2, name: '机器视觉', slug: 'vision', description: '视觉算法', sort_order: 1, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
];
const topics = [
  { id: 1, category_id: 1, name: 'Optimizer', slug: 'optimizer', description: '优化器', sort_order: 0, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
  { id: 2, category_id: 2, name: '目标检测', slug: 'detection', description: 'YOLO', sort_order: 0, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
];
const drafts = [
  {
    id: 7,
    revision: 1,
    source_status: 'pending',
    source_document_id: 86,
    source_title: '让炼丹更科学一些（九）：经典自适应梯度算法',
    source_name: '科学空间',
    source_url: 'https://example.com/optimizer',
    source_content_hash: 'a'.repeat(64),
    topic_id: 1,
    status: 'draft',
    title: 'Adam 优化器的核心机制',
    summary: 'Adam 结合梯度的一阶矩与二阶矩估计，为每个参数自适应调整学习率。它通过偏差修正减轻初始阶段估计偏小的问题。',
    difficulty: 'intermediate',
    key_points: ['一阶矩估计对梯度进行指数移动平均。', '二阶矩估计用于调整每个参数的更新幅度。', '偏差修正在训练初期尤其重要。'],
    quiz_items: [
      { question: 'Adam 同时维护哪两类统计量？', answer: '梯度的一阶矩估计和二阶矩估计。' },
      { question: '为什么需要偏差修正？', answer: '因为零初始化的移动平均在训练初期会偏向零。' },
    ],
    model: 'qwen-plus',
    prompt_version: 'draft-v1',
    generation_count: 2,
    generated_at: '2026-09-24T05:20:00Z',
    reviewed_at: null,
    knowledge_point_id: null,
    created_at: '2026-09-24T05:00:00Z',
    updated_at: '2026-09-24T05:20:00Z',
  },
];

async function main() {
  const outputDir = path.join(__dirname, 'drafts');
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
          if (url.pathname.endsWith('/knowledge-drafts')) return route.fulfill({ json: drafts });
          if (url.pathname.endsWith('/categories')) return route.fulfill({ json: categories });
          if (url.pathname.endsWith('/topics')) return route.fulfill({ json: topics });
          return route.fulfill({ status: 404, json: { error: { message: 'Unknown fixture route' } } });
        });
        const page = await context.newPage();
        const errors = [];
        page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
        page.on('pageerror', (error) => errors.push(error.message));
        const response = await page.goto('http://localhost:3001/drafts?draft=7', { waitUntil: 'networkidle', timeout: 60000 });
        const name = `${device.name}-${theme}-drafts`;
        await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage: true, animations: 'disabled' });
        const layout = await page.evaluate(() => ({
          viewportWidth: innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
          heading: document.querySelector('h1')?.textContent || null,
          selectedTopic: document.querySelector('select')?.value || null,
          title: document.querySelector('input')?.value || null,
          keyPointCount: document.querySelectorAll('ol[class*="keyPoints"] li').length,
          quizCount: document.querySelectorAll('div[class*="quizList"] article').length,
          approvalAction: Array.from(document.querySelectorAll('button')).some((button) => button.textContent?.includes('批准入库')),
          activeNavigation: document.querySelector('a[aria-current="page"]')?.textContent?.trim() || null,
        }));
        results.push({ name, status: response?.status(), ...layout, errors });
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  await fs.writeFile(path.join(outputDir, 'results.json'), `${JSON.stringify(results, null, 2)}\n`);
  const failed = results.some((item) => item.status !== 200 || item.horizontalOverflow || item.errors.length || item.heading !== 'AI 先打草稿，你来定稿。' || item.selectedTopic !== '1' || item.title !== 'Adam 优化器的核心机制' || item.keyPointCount !== 3 || item.quizCount !== 2 || !item.approvalAction || item.activeNavigation !== '草稿审核');
  console.log(JSON.stringify(results, null, 2));
  if (failed) process.exitCode = 1;
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
