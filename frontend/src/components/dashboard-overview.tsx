"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { draftApi, knowledgeApi, reviewApi } from "@/lib/api";
import type { Category, KnowledgePoint, ReviewOverview, Topic } from "@/lib/types";
import { AnalysisPanel } from "./analysis-panel";
import { Icon, type IconName } from "./icon";
import styles from "./dashboard-overview.module.css";

type LibraryData = { categories: Category[]; topics: Topic[]; points: KnowledgePoint[] };

export function DashboardOverview() {
  const [data, setData] = useState<LibraryData | null>(null);
  const [offline, setOffline] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [workflow, setWorkflow] = useState<{ drafts: number; review: ReviewOverview } | null>(null);
  const [workflowError, setWorkflowError] = useState(false);

  const fetchWorkflow = useCallback(() => Promise.all([draftApi.list(), reviewApi.overview()])
    .then(([drafts, review]) => ({ drafts: drafts.filter((draft) => draft.status === "draft" && draft.source_status === "pending").length, review })), []);

  useEffect(() => {
    let cancelled = false;
    fetchWorkflow().then((value) => { if (!cancelled) { setWorkflow(value); setWorkflowError(false); } })
      .catch(() => { if (!cancelled) setWorkflowError(true); });
    return () => { cancelled = true; };
  }, [fetchWorkflow]);

  const fetchLibrary = useCallback(() => Promise.all([
    knowledgeApi.listCategories(), knowledgeApi.listTopics(), knowledgeApi.listKnowledgePoints(),
  ]).then(([categories, topics, points]) => ({ categories, topics, points })), []);

  useEffect(() => {
    let cancelled = false;
    fetchLibrary().then((value) => {
      if (!cancelled) { setData(value); setOffline(false); }
    }).catch(() => { if (!cancelled) setOffline(true); });
    return () => { cancelled = true; };
  }, [fetchLibrary]);

  async function retry() {
    setRetrying(true);
    try { setData(await fetchLibrary()); setOffline(false); }
    catch { setOffline(true); }
    finally { setRetrying(false); }
  }

  const recent = data?.points.toSorted((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)).slice(0, 4) ?? [];
  const metrics: { label: string; detail: string; icon: IconName; count?: number; style: string }[] = [
    { label: "探索的领域", detail: "为好奇心留一席之地", icon: "folder", count: data?.categories.length, style: styles.lime },
    { label: "串联的主题", detail: "让零散想法有条有理", icon: "layers", count: data?.topics.length, style: styles.lilac },
    { label: "积累的知识点", detail: "每一个小点，都算数", icon: "leaf", count: data?.points.length, style: styles.peach },
  ];

  return (
    <div className={styles.dashboard}>
      <div className={styles.featureRow}>
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <span className={styles.heroLabel}><span />一点一滴，积累成自己的底气</span>
            <h2 id="hero-title">把学过的，<br />变成<span className={styles.highlight}>自己的。</span></h2>
            <p>不止收藏，更要真正掌握。<br />从整理一个小知识点开始。</p>
            <Link href="/knowledge" className="button button-dark">整理我的知识<Icon name="arrow-up-right" size={17} /></Link>
          </div>
          <KnowledgeSketch />
          <span className={styles.heroIndex}>01 / GROW YOUR MIND</span>
        </section>
        <aside className={styles.memo}>
          <div className={styles.memoTop}><span>给今天的你</span><Icon name="sun" size={20} /></div>
          <div className={styles.memoQuote}>学得慢一点，<br />也没关系。<br /><span>记得久一点就好。</span></div>
          <div className={styles.memoBottom}><span className={styles.memoLine} /><span>积累有自己的节奏</span></div>
          <span className={styles.memoNumber}>NOTE / 001</span>
        </aside>
      </div>

      {offline && <div className={styles.connectionError} role="alert"><span>API 尚未连接，暂时无法读取你的知识库。</span><button type="button" onClick={retry} disabled={retrying}><Icon name="refresh" size={14} />{retrying ? "连接中…" : "重新连接"}</button></div>}

      <section className={styles.workflow} aria-label="今天的学习安排">
        <Link href="/drafts"><Icon name="draft" size={22} /><div><strong>核对 AI 草稿</strong><small>{workflowError ? "打开审核页重新读取" : workflow ? `${workflow.drafts} 份等待你的确认` : "正在读取…"}</small></div><Icon name="arrow-up-right" size={18} /></Link>
        <Link href="/review"><Icon name="refresh" size={22} /><div><strong>{workflow?.review.active_session_id ? "继续上次复习" : "开始每日复习"}</strong><small>{workflowError ? "打开复习页重新读取" : workflow ? `${workflow.review.due_count} 个知识点待复习 · 今日已答 ${workflow.review.reviewed_today} 题` : "正在读取…"}</small></div><Icon name="arrow-up-right" size={18} /></Link>
      </section>

      <section className={styles.metrics} aria-label="知识结构统计" aria-busy={!data && !offline}>
        {metrics.map((metric) => (
          <div className={styles.metric} key={metric.label}>
            <span className={styles.metricIcon + " " + metric.style}><Icon name={metric.icon} size={22} /></span>
            <div className={styles.metricText}><span>{metric.label}</span><small>{metric.detail}</small></div>
            <strong>{metric.count !== undefined ? String(metric.count).padStart(2, "0") : "—"}</strong>
          </div>
        ))}
      </section>

      <AnalysisPanel />

      <div className={styles.libraryRow}>
        <section className={styles.library} aria-labelledby="library-heading">
          <div className={styles.sectionHeading}><div><h2 id="library-heading">我的知识版图<span className={styles.titleDot} /></h2><p>让好奇心有方向，让知识有连接。</p></div><Link href="/knowledge" className={styles.textLink}>进入知识库<Icon name="arrow-up-right" size={16} /></Link></div>
          {!data && !offline ? <div className={styles.loading} role="status"><span className={styles.skeleton} /><span className={styles.skeleton} />正在读取你的知识库…</div> :
            data?.categories.length ? (
              <div className={styles.domainGrid}>
                {data.categories.slice(0, 4).map((category, index) => {
                  const topics = data.topics.filter((topic) => topic.category_id === category.id);
                  const ids = new Set(topics.map((topic) => topic.id));
                  const count = data.points.filter((point) => ids.has(point.topic_id)).length;
                  return <Link href={"/knowledge?category=" + category.id} className={styles.domainCard} key={category.id}>
                    <div className={styles.domainTop}><span className={styles.domainIcon + " " + [styles.lime, styles.lilac, styles.peach, styles.sage][index % 4]}><Icon name={index % 2 ? "book" : "folder"} size={20} /></span><Icon name="arrow-up-right" size={17} /></div>
                    <h3>{category.name}</h3><p>{category.description || "你的好奇心，正在这里生长。"}</p>
                    <div className={styles.domainMeta}><span>{topics.length} 个主题</span><span>{count} 个知识点</span></div>
                  </Link>;
                })}
                <Link href="/knowledge?new=category#new-category" className={styles.addDomain}><Icon name="plus" size={20} /><span>开启一个新领域</span><small>还有什么让你好奇？</small></Link>
              </div>
            ) : (
              <div className={styles.emptyLibrary}>
                <div className={styles.emptyIllustration} aria-hidden="true"><div className={styles.emptyOrbit} /><span className={styles.emptyFolder}><Icon name="folder" size={44} /></span><span className={styles.emptySpark}>✳</span><span className={styles.emptySeed} /></div>
                <h3>{offline ? "你的知识，会在这里相遇。" : "这里，留给你的无限可能。"}</h3>
                <p>{offline ? "连接恢复后，就能继续探索你的知识版图。" : "代码、设计、语言，或任何让你眼睛发亮的事。"}</p>
                {!offline && <Link href="/knowledge?new=category#new-category" className="button button-lime"><Icon name="plus" size={16} />创建第一个领域</Link>}
                <span className={styles.emptyFootnote}>你的下一次「原来如此」，从这里开始。</span>
              </div>
            )
          }
        </section>

        <aside className={styles.recent} aria-labelledby="recent-heading">
          <div className={styles.sectionHeading}><div><h2 id="recent-heading">{recent.length ? "最近拾获" : "从这里，开始生长"}</h2><p>{recent.length ? "温故知新，常看常新。" : "一棵知识树，只需要三小步。"}</p></div><Icon name={recent.length ? "clock" : "leaf"} size={19} /></div>
          {recent.length ? <ul className={styles.recentList}>{recent.map((point) => {
            const topic = data?.topics.find((item) => item.id === point.topic_id);
            return <li key={point.id}><Link href={"/knowledge?category=" + (topic?.category_id ?? "") + "&topic=" + point.topic_id + "&point=" + point.id + "#knowledge-point-" + point.id}><span className={styles.recentBullet} /><div><strong>{point.name}</strong><small>{topic?.name || "知识点"}</small></div><Icon name="arrow-up-right" size={15} /></Link></li>;
          })}</ul> : <ol className={styles.steps}>
            <li><span>01</span><div><strong>圈定一个领域</strong><p>从你正在学的、感兴趣的开始。</p></div></li>
            <li><span>02</span><div><strong>拆成几个小主题</strong><p>把大的方向，变成清晰的线索。</p></div></li>
            <li><span>03</span><div><strong>留下一个知识点</strong><p>用自己的话，记下新的理解。</p></div></li>
          </ol>}
          <div className={styles.mindset}><span>LESS, BUT BETTER.</span><p>不必一次整理所有知识。<br />今天的一小步，就很好。</p><Icon name="arrow-up-right" size={24} /></div>
        </aside>
      </div>
    </div>
  );
}

function KnowledgeSketch() {
  return (
    <div className={styles.sketch} aria-hidden="true">
      <svg viewBox="0 0 390 290" fill="none">
        <ellipse cx="210" cy="241" rx="118" ry="14" fill="#dce5c7" opacity=".5" />
        <path d="M64 188c-16-58 69-127 162-98s108 118 39 137" stroke="#9aab7c" strokeWidth="1.2" strokeDasharray="4 7" />
        <g transform="rotate(-12 184 177)">
          <rect x="102" y="123" width="173" height="104" rx="7" fill="#d4dfbc" stroke="#303a24" strokeWidth="1.8" />
          <path d="M102 210h173v13a5 5 0 0 1-5 5H109a7 7 0 0 1-7-7z" fill="#f8f9ef" stroke="#303a24" strokeWidth="1.8" />
          <path d="M111 216h152 M111 222h144 M121 123v87" stroke="#303a24" strokeWidth="1.2" />
          <rect x="143" y="146" width="103" height="40" rx="2" fill="#eef2df" stroke="#303a24" strokeWidth="1.2" />
          <path d="M159 158h68 M173 170h39" stroke="#667451" strokeWidth="2" strokeLinecap="round" />
          <path d="M239 210v26l9-5 8 5v-26" fill="#d0f266" stroke="#303a24" strokeWidth="1.5" />
        </g>
        <g transform="rotate(10 213 104)">
          <rect x="141" y="59" width="144" height="96" rx="5" fill="#fffef8" stroke="#303a24" strokeWidth="1.7" />
          <rect x="160" y="80" width="29" height="29" rx="3" fill="#d0f266" />
          <path d="m167 94 5 5 10-12" stroke="#303a24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M201 85h61 M201 96h42 M160 125h102 M160 136h72" stroke="#9aa18d" strokeWidth="1.3" strokeLinecap="round" />
        </g>
        <path d="m102 61 7-17 7 17 17 7-17 7-7 17-7-17-17-7z" fill="#d0f266" stroke="#303a24" strokeWidth="1.4" />
        <path d="m302 157 4-11 4 11 11 4-11 4-4 11-4-11-11-4z" fill="#d0f266" stroke="#303a24" strokeWidth="1.3" />
        <path d="M315 75c11 8 12 19 5 27m-5-6 5 7 8-5 M70 229l-5 9m11-4-1 8" stroke="#667451" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="63" cy="123" r="4" fill="#b3c987" /><circle cx="281" cy="37" r="3" fill="#9bad80" />
        <g transform="rotate(-5 220 48)"><rect x="177" y="27" width="104" height="24" rx="12" fill="#d0f266" stroke="#303a24" strokeWidth="1" /><text x="229" y="43" textAnchor="middle" fill="#303a24" fontSize="10" fontFamily="sans-serif" letterSpacing="1">KEEP GROWING</text></g>
      </svg>
    </div>
  );
}
