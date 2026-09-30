"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { reviewApi } from "@/lib/api";
import type { ReviewItem, ReviewOverview, ReviewRating, ReviewSession } from "@/lib/types";
import { SourceContent } from "./source-content";
import { useUnsavedChanges } from "./use-unsaved-changes";
import styles from "./learning.module.css";

const ratings: { value: ReviewRating; label: string; hint: string }[] = [
  { value: "again", label: "没记住", hint: "10 分钟后再来" },
  { value: "hard", label: "有点吃力", hint: "明天再巩固" },
  { value: "good", label: "基本掌握", hint: "提升一个等级" },
  { value: "easy", label: "很熟练", hint: "提升两个等级" },
];
function dateLabel(value: string | null) {
  if (!value) return "首次复习";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function ReviewWorkspace() {
  const [overview, setOverview] = useState<ReviewOverview | null>(null);
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestedPoint, setRequestedPoint] = useState<number | undefined>();

  useEffect(() => {
    let cancelled = false;
    const query = new URLSearchParams(window.location.search);
    const sessionId = Number(query.get("session"));
    Promise.all([reviewApi.overview(), sessionId ? reviewApi.getSession(sessionId) : reviewApi.active()])
      .then(([stats, current]) => {
        if (cancelled) return;
        setOverview(stats); setSession(current);
        setRequestedPoint(Number(query.get("point")) || undefined);
      })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "复习数据读取失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function mutate(action: () => Promise<ReviewSession>) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const result = await action();
      setSession(result);
      window.history.replaceState(null, "", `/review?session=${result.id}`);
      setOverview(await reviewApi.overview());
    } catch (reason) { setError(reason instanceof Error ? reason.message : "这一步没有完成，请重试"); }
    finally { setBusy(false); }
  }

  const current = session?.items.find((item) => !item.rating);
  const completedCount = session?.items.filter((item) => item.rating).length ?? 0;
  const selectedPoint = overview?.points.find((point) => point.knowledge_point_id === requestedPoint);
  const levels = [1, 2, 3, 4, 5].map((level) => overview?.points.filter((point) => point.level === level).length ?? 0);

  return <div className={styles.stack}>
    {error && <div className={styles.error} role="alert">{error} <button className={styles.textButton} onClick={() => window.location.reload()} disabled={busy}>重新载入</button></div>}
    <div className={styles.stats} aria-label="复习统计">
      <div className={styles.stat}><strong>{overview?.due_count ?? "—"}</strong><span>待复习知识点</span></div>
      <div className={styles.stat}><strong>{overview?.reviewed_today ?? "—"}</strong><span>今日已答题</span></div>
      <div className={styles.stat}><strong>{overview?.completed_sessions ?? "—"}</strong><span>已完成轮次</span></div>
    </div>
    {loading ? <p className={styles.panel} role="status">正在准备复习…</p> : current && session ?
      <section className={styles.panel} aria-label="当前复习">
        <div className={styles.toolbar}><span className={styles.eyebrow}>{current.topic_name} / {current.point_name}</span><span className={styles.muted}>{completedCount + 1} / {session.items.length}</span></div>
        <progress className={styles.progress} value={completedCount} max={session.items.length} aria-label="本轮复习进度" />
        <QuestionCard key={current.id} item={current} busy={busy} onReveal={(answer) => void mutate(() => reviewApi.reveal(current.id, answer))} onRate={(answer, rating) => void mutate(() => reviewApi.answer(current.id, answer, rating))} />
        <p className={styles.muted}>进度会在查看答案和自评时保存，可稍后回来继续。</p>
      </section> : <section className={styles.panel}>
        {session?.status === "completed" ? <>
          <span className={styles.eyebrow}>SESSION COMPLETE</span><h2>这一轮，已经记下了。</h2>
          <p className={styles.muted}>完成 {session.items.length} 道题。下次复习按每个知识点中最吃力的那道题安排。</p>
          <details className={styles.question}><summary>查看本轮作答记录</summary>{session.items.map((item) => <div className={styles.question} key={item.id}><strong>{item.question}</strong><p>我的回答：{item.user_answer || "未填写"}</p><SourceContent content={item.standard_answer ?? ""} /><small className={styles.muted}>自评：{ratings.find((rating) => rating.value === item.rating)?.label}</small></div>)}</details>
        </> : <><span className={styles.eyebrow}>A LITTLE EVERY DAY</span><h2>{selectedPoint ? `今天复习：${selectedPoint.name}` : overview?.due_count ? "从今天该复习的开始。" : "给记忆一点时间。"}</h2><p className={styles.muted}>先试着用自己的话回答，再对照标准答案，选择真实的掌握程度。</p></>}
        {overview && (overview.due_count > 0 || selectedPoint || overview.active_session_id) ?
          <button className="button button-dark" disabled={busy} onClick={() => void mutate(() => reviewApi.start(selectedPoint?.knowledge_point_id))}>{busy ? "准备中…" : overview.active_session_id ? "继续上次复习" : selectedPoint ? "开始这个知识点" : "开始今日复习"}</button>
          : <div className={styles.empty}><p>{overview?.points.length ? "当前没有到期的知识点，也可以在下方选择一个提前练习。" : "还没有可复习的题目。为现有知识点添加题目，或批准一份 AI 草稿，就可以开始。"}</p><Link className="button button-lime" href="/knowledge">前往知识库</Link></div>}
      </section>}

    {overview && <section id="progress" className={styles.panel}>
      <div className={styles.toolbar}><div><span className={styles.eyebrow}>YOUR PROGRESS</span><h2>知识掌握与下次复习</h2></div><span className={styles.muted}>{overview.points.length} 个有题目的知识点</span></div>
      {!!overview.points.length && <div className={styles.levelBars} aria-label="L1 到 L5 掌握等级分布">{levels.map((count, index) => <div key={index}><span>{count}</span><i style={{ height: `${Math.max(4, count / Math.max(1, ...levels) * 90)}px` }} /><span>L{index + 1}</span></div>)}</div>}
      <ul className={styles.pointList}>{overview.points.map((point) => <li key={point.knowledge_point_id}>
        <div><Link href={`/knowledge/detail?point=${point.knowledge_point_id}`}>{point.name}</Link><small><span className={styles.level}>L{point.level}</span>{point.topic_name} · {point.question_count} 道题 · 复习 {point.review_count} 次<br />{point.is_due ? "待复习" : "下次"} · {dateLabel(point.due_at)}</small></div>
        <button className="button button-lime" disabled={busy || session?.status === "active"} onClick={() => void mutate(() => reviewApi.start(point.knowledge_point_id))}>练习</button>
      </li>)}</ul>
      {!!overview.recent_sessions?.length && <details className={styles.question}><summary>最近完成的复习</summary><ul className={styles.pointList}>{overview.recent_sessions.map((history) => <li key={history.id}><span>{dateLabel(history.completed_at)} · {history.question_count} 道题</span><button className={styles.textButton} disabled={busy || session?.status === "active"} onClick={() => void mutate(() => reviewApi.getSession(history.id))}>查看记录</button></li>)}</ul>{session?.status === "active" && <p className={styles.muted}>完成当前复习后，可在这里回看历史答案。</p>}</details>}
      <details className={styles.question}><summary>复习时间如何安排？</summary><p className={styles.muted}>这是便于坚持的固定规则：没记住回到 L1，10 分钟后再复习；有点吃力降一级，明天再复习；基本掌握升一级，很熟练升两级，最高 L5。L2、L3、L4、L5 分别间隔 3、7、14、30 天。同一知识点的多道题按最低自评分计算一次，改题后从新题开始。</p></details>
    </section>}
  </div>;
}

function QuestionCard({ item, busy, onReveal, onRate }: {
  item: ReviewItem; busy: boolean; onReveal: (answer: string) => void;
  onRate: (answer: string, rating: ReviewRating) => void;
}) {
  const [answer, setAnswer] = useState(item.user_answer);
  useUnsavedChanges(answer !== item.user_answer && !busy);
  return <>
    <div className={styles.questionTitle}><SourceContent ariaLabel="复习问题" content={item.question} /></div>
    <label className={styles.answerLabel}>我的回答<textarea aria-label="我的回答" rows={5} maxLength={10000} placeholder="先写下你的理解，也可以在心里作答。" disabled={busy} value={answer} onChange={(event) => setAnswer(event.target.value)} /></label>
    {item.standard_answer === null ? <button className="button button-dark" disabled={busy} onClick={() => onReveal(answer)}>{busy ? "正在保存…" : "查看标准答案"}</button> : <>
      <div className={styles.standardAnswer}><span className={styles.eyebrow}>标准答案</span><SourceContent content={item.standard_answer} /></div>
      <p className={styles.muted}>对照答案后，这道题掌握得怎么样？</p>
      <div className={styles.ratings}>{ratings.map((rating) => <button key={rating.value} disabled={busy} onClick={() => onRate(answer, rating.value)}><strong>{rating.label}</strong><small>{rating.hint}</small></button>)}</div>
    </>}
  </>;
}
