"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { knowledgeApi, sourceApi } from "@/lib/api";
import type { Difficulty, KnowledgePoint, KnowledgePointEdit, SourceDocument, Topic } from "@/lib/types";
import { SourceContent } from "./source-content";
import { useUnsavedChanges } from "./use-unsaved-changes";
import styles from "./learning.module.css";

const difficultyNames = { beginner: "入门", intermediate: "进阶", advanced: "深入" };
function editable(point: KnowledgePoint): KnowledgePointEdit {
  return { name: point.name, summary: point.summary, description: point.description,
    difficulty: point.difficulty, key_points: point.key_points ?? [], quiz_items: point.quiz_items ?? [] };
}

export function KnowledgeDetail() {
  const [point, setPoint] = useState<KnowledgePoint | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [draft, setDraft] = useState<KnowledgePointEdit | null>(null);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const dirty = editing && !!draft && !!point && JSON.stringify(draft) !== JSON.stringify(editable(point));
  useUnsavedChanges(dirty);

  useEffect(() => {
    let cancelled = false;
    const id = Number(new URLSearchParams(window.location.search).get("point"));
    Promise.all([knowledgeApi.getKnowledgePoint(id), knowledgeApi.listTopics()])
      .then(async ([next, nextTopics]) => {
        if (cancelled) return;
        setPoint(next); setDraft(editable(next)); setTopics(nextTopics);
        const originals = await Promise.all((next.source_document_ids ?? []).map(sourceApi.getDocument));
        if (!cancelled) setSources(originals);
      })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : "知识点读取失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function save() {
    if (!point || !draft || busy) return;
    setBusy(true); setError("");
    try {
      const next = await knowledgeApi.updateKnowledgeContent(point.id, {
        ...draft, name: draft.name.trim(), summary: draft.summary?.trim() || null,
        key_points: draft.key_points?.map((item) => item.trim()).filter(Boolean) ?? [],
      });
      setPoint(next); setDraft(editable(next)); setEditing(false);
      setNotice("已保存。题目发生变化时，下次复习将使用新题目。");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  }

  const topic = topics.find((item) => item.id === point?.topic_id);
  const quiz = draft?.quiz_items ?? [];
  const valid = !!draft?.name.trim() && quiz.every((item) => item.question.trim() && item.answer.trim());
  if (loading) return <p role="status" className={styles.panel}>正在读取知识内容…</p>;
  return <div className={styles.stack}>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {notice && <p role="status" className={styles.notice}>{notice}</p>}
    <div className={styles.toolbar}><Link href={`/knowledge?category=${topic?.category_id ?? ""}&topic=${point?.topic_id ?? ""}`}>← 返回知识库</Link>
      {point && <div className={styles.actions}>
        {!!point.quiz_items?.length && <Link className="button button-dark" href={`/review?point=${point.id}`}>复习这个知识点</Link>}
        <button className="button button-lime" disabled={busy} onClick={() => {
          if (editing && dirty && !window.confirm("放弃尚未保存的修改？")) return;
          setDraft(editable(point)); setEditing(!editing);
        }}>{editing ? "取消编辑" : "编辑内容与题目"}</button>
      </div>}
    </div>
    {point && draft && <>
      <section className={styles.panel}>
        <span className={styles.eyebrow}>{topic?.name ?? "知识点"}{point.difficulty ? ` / ${difficultyNames[point.difficulty]}` : ""}</span>
        {editing ? <div className={styles.form}>
          <label>知识点名称<input maxLength={160} value={draft.name} disabled={busy} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
          <label>难度<select value={draft.difficulty ?? ""} disabled={busy} onChange={(e) => setDraft({ ...draft, difficulty: (e.target.value || null) as Difficulty | null })}><option value="">未设置</option>{Object.entries(difficultyNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
          <label>摘要<textarea rows={5} maxLength={6000} value={draft.summary ?? ""} disabled={busy} onChange={(e) => setDraft({ ...draft, summary: e.target.value })} /></label>
          <label>我的笔记<textarea rows={5} value={draft.description ?? ""} disabled={busy} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></label>
          <label>核心要点（每行一条）<textarea rows={5} value={draft.key_points?.join("\n") ?? ""} disabled={busy} onChange={(e) => setDraft({ ...draft, key_points: e.target.value.split("\n") })} /></label>
        </div> : <>
          <h2>{point.name}</h2>
          {point.summary && <SourceContent content={point.summary} ariaLabel="知识摘要" />}
          {point.description && point.description !== point.summary && <><h3>我的笔记</h3><SourceContent content={point.description} /></>}
          {!!point.key_points?.length && <><h3>核心要点</h3><ol className={styles.keyPoints}>{point.key_points.map((item, index) => <li key={index}><SourceContent content={item} /></li>)}</ol></>}
          {!point.summary && !point.description && <p className={styles.muted}>还没有内容，点击“编辑内容与题目”补充你的理解。</p>}
        </>}
      </section>
      <section className={styles.panel} aria-label="复习题目">
        <div className={styles.toolbar}><h2>题目与标准答案</h2>{editing && quiz.length < 5 && <button className="button button-lime" disabled={busy} onClick={() => setDraft({ ...draft, quiz_items: [...quiz, { question: "", answer: "" }] })}>添加题目</button>}</div>
        {editing ? quiz.map((item, index) => <div className={styles.questionEditor} key={index}>
          <span className={styles.eyebrow}>Q{index + 1}</span>
          <label>问题<input maxLength={500} value={item.question} disabled={busy} onChange={(e) => setDraft({ ...draft, quiz_items: quiz.map((q, i) => i === index ? { ...q, question: e.target.value } : q) })} /></label>
          <label>标准答案<textarea rows={3} maxLength={2000} disabled={busy} value={item.answer} onChange={(e) => setDraft({ ...draft, quiz_items: quiz.map((q, i) => i === index ? { ...q, answer: e.target.value } : q) })} /></label>
          <button className={styles.textButton} disabled={busy} onClick={() => setDraft({ ...draft, quiz_items: quiz.filter((_, i) => i !== index) })}>移除这道题</button>
        </div>) : (point.quiz_items ?? []).map((item, index) => <details className={styles.question} key={index}><summary><span>Q{index + 1}</span>{item.question}</summary><SourceContent ariaLabel={`第${index + 1}题标准答案`} content={item.answer} /></details>)}
        {!quiz.length && <p className={styles.muted}>这个知识点还没有题目。可以手动补充，或者从资料生成并审核 AI 草稿。</p>}
        {editing && <button className="button button-dark" disabled={busy || !valid} onClick={() => void save()}>{busy ? "正在保存…" : "保存内容"}</button>}
      </section>
      {!!sources.length && <section className={styles.panel}><h2>来源与原文</h2>{sources.map((source) => <details className={styles.question} key={source.id}><summary>{source.source_name} · {source.title}</summary><Link href={`/sources?source=${source.id}&status=${source.status}`}>在资料收件箱中查看</Link><SourceContent content={source.content} /></details>)}</section>}
    </>}
  </div>;
}
