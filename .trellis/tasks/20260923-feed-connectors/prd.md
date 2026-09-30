# RSSHub / RSS ingestion and Crawl4AI cleaning

## Goal

把公网 RSS/Atom 与 RSSHub 路由接入现有资料收件箱；用户可管理订阅源、手动同步，
并按订阅源选择直接使用 Feed 正文、自动按需调用 Crawl4AI，或强制用 Crawl4AI 清洗原文链接。

## What I already know

- 现有 `source_documents` 已实现状态、Hash 去重、日序同步和资料转知识点。
- 用户已确认下一阶段从 RSSHub/Crawl4AI 开始；MediaCrawler 需要平台账号/Cookie，后置。
- 腾讯云 VPS 总内存 3.6 GiB，当前可用约 1.6 GiB，浏览器抓取必须单并发并设内存上限。
- 同步必须由用户显式触发；本阶段不创建后台定时任务。

## Requirements

- 管理 RSS 与 RSSHub 订阅源：创建、编辑、启用/停用、列表。
- RSS 使用完整公网 `http/https` URL；RSSHub 使用以 `/` 开头的路由，由后端拼接可信 `RSSHUB_BASE_URL`。
- 支持 `feed`、`auto`、`crawl4ai` 三种清洗模式。
- 单次最多处理可配置数量的最新条目，默认 30；Feed 滚动窗口不会把旧资料标记 stale。
- Feed 获取、XML 解析、Crawl4AI 清洗任一失败都产生稳定错误，不破坏已有资料。
- `auto` 模式在 Feed 正文足够长时不启动浏览器；Crawl4AI 不可用时回退 Feed 正文并统计失败。
- 资料记录来源名称、原文 URL、作者，并继续复用现有 pending/accepted/ignored/stale 流程。
- 来源管理页面沿用知衡纸张、墨绿、克制排版；显示最近同步时间、状态、条目统计与错误。
- Compose 提供不暴露公网端口的 RSSHub 与 Crawl4AI 可选 profile；Crawl4AI Bearer Token 仅后端可见。

## Acceptance Criteria

- [ ] 创建普通 RSS 和 RSSHub 路由时完成不同格式校验。
- [ ] 同一 Feed 连续同步不会创建重复资料；GUID 缺失时稳定回退到链接或内容哈希。
- [ ] 首次同步、内容更新、无变化、部分清洗失败均有测试。
- [ ] 公网 Feed URL 阻止 localhost、私网、链路本地与非 HTTP(S) 地址。
- [ ] Crawl4AI 客户端兼容常见 `results/result/direct` 响应与 Markdown 字符串/对象形态。
- [ ] `/feeds` 页面可创建、编辑、停用、单独同步和同步全部已启用来源。
- [ ] `/sources` 正确显示日序或订阅源名称、作者与原文链接。
- [ ] 后端测试、Alembic 空库升级、前端 lint/build、桌面和移动视觉检查通过。

## Definition of Done

- 代码、迁移、Compose、`.env.example`、README 和 code-spec 同步。
- 外部调用有超时、大小上限、SSRF 防护与可测试的错误边界。
- 本地验证完成；线上重启前再次列出动作并等待确认。

## Technical Approach

- 新表 `feed_sources` 保存配置与最近同步状态；`source_documents.feed_source_id` 建立可追溯关系。
- `feedparser` 解析 RSS/Atom，`BeautifulSoup` 把 Feed HTML 转成稳定文本。
- Feed provider 使用 `feed:{feed_source_id}`；外部 ID 优先 GUID，其次 canonical link，最后内容哈希。
- Crawl4AI 只接收后端已验证的公网文章 URL，请求最小化为 `POST /crawl {"urls":[url]}`。
- 同步先完整获取/解析，再在事务中 upsert；Feed 不执行 missing→stale。

## Decision (ADR-lite)

**Context**: RSSHub 是 Feed 生成器，Crawl4AI 是成本更高的浏览器正文清洗器；全部条目强制浏览器抓取会超出当前 VPS 资源余量。

**Decision**: 默认 `auto`，优先使用已有 Feed 正文，仅在正文过短时调用 Crawl4AI；容器单并发、内部网络、Token 认证。

**Consequences**: 资源占用可控，普通 RSS 即使 Crawl4AI 离线仍能同步；少数 Feed 的摘要可能需要用户切换到强制清洗。

## Out of Scope

- MediaCrawler 及平台账号、Cookie、验证码管理。
- 定时同步、消息队列、关键词过滤、Embedding、LLM 质量判断。
- 自动接受资料或自动生成知识点。

## Research Notes

- RSSHub 官方仓库与镜像：<https://github.com/DIYgod/RSSHub>、<https://github.com/diygod/RSSHub/pkgs/container/rsshub>
- Crawl4AI 官方 Docker API：<https://github.com/unclecode/crawl4ai/blob/main/deploy/docker/README.md>
- Crawl4AI 0.9 起默认开启认证；跨容器访问必须配置 `CRAWL4AI_API_TOKEN`。
- 官方 `/crawl` 支持最小 `{"urls":[...]}` 请求；客户端必须检查每条结果的 `success` 和 Markdown 内容。

