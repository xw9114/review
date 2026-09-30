"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Icon } from "@/components/icon";
import { SourceContent } from "@/components/source-content";
import { SourceQuality } from "@/components/source-quality";
import { useUnsavedChanges } from "@/components/use-unsaved-changes";
import { draftApi, knowledgeApi, sourceApi } from "@/lib/api";
import type {
  Category,
  Difficulty,
  DraftStatus,
  KnowledgeDraft,
  KnowledgeDraftReview,
  QuizItem,
  SourceDocument,
  Topic,
} from "@/lib/types";

import styles from "./draft-review.module.css";

type DraftForm = KnowledgeDraftReview;
type Filter = "all" | DraftStatus;

const difficultyLabels: Record<Difficulty, string> = {
  beginner: "入门",
  intermediate: "进阶",
  advanced: "深入",
};

const statusLabels: Record<DraftStatus, string> = {
  draft: "待审核",
  approved: "已批准",
  rejected: "已退回",
  stale: "已过期",
};

function formFromDraft(draft: KnowledgeDraft): DraftForm {
  return {
    expected_revision: draft.revision,
    topic_id: draft.topic_id ?? 0,
    title: draft.title,
    summary: draft.summary,
    difficulty: draft.difficulty,
    key_points: [...draft.key_points],
    quiz_items: draft.quiz_items.map((item) => ({ ...item })),
  };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function DraftReview() {
  const [drafts, setDrafts] = useState<KnowledgeDraft[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<DraftForm | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [original, setOriginal] = useState<SourceDocument | null>(null);
  const [readingOriginal, setReadingOriginal] = useState(false);

  const selectDraft = useCallback((draft: KnowledgeDraft) => {
    setSelectedId(draft.id);
    setForm(formFromDraft(draft));
    setError("");
    setNotice("");
    setOriginal(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([draftApi.list(), knowledgeApi.listCategories(), knowledgeApi.listTopics()])
      .then(([loadedDrafts, loadedCategories, loadedTopics]) => {
        if (cancelled) return;
        setDrafts(loadedDrafts);
        setCategories(loadedCategories);
        setTopics(loadedTopics);
        const requested = Number(new URLSearchParams(window.location.search).get("draft"));
        const initial = loadedDrafts.find((draft) => draft.id === requested) ?? loadedDrafts[0] ?? null;
        if (initial) selectDraft(initial);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "草稿读取失败。");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectDraft]);

  const visibleDrafts = useMemo(
    () => filter === "all" ? drafts : drafts.filter((draft) => draft.status === filter),
    [drafts, filter],
  );
  const selected = drafts.find((draft) => draft.id === selectedId) ?? null;
  const editable = selected?.source_status === "pending" && selected.status !== "approved" && selected.status !== "stale";
  const dirty = Boolean(selected && form && JSON.stringify(form) !== JSON.stringify(formFromDraft(selected)));
  useUnsavedChanges(dirty);

  function chooseDraft(draft: KnowledgeDraft) {
    if (draft.id === selectedId || busy || readingOriginal) return;
    if (dirty && !window.confirm("草稿修改尚未保存，仍要切换吗？")) return;
    selectDraft(draft);
  }

  function changeFilter(next: Filter) {
    if (next === filter || busy || readingOriginal) return;
    if (dirty && !window.confirm("草稿修改尚未保存，仍要切换吗？")) return;
    setFilter(next);
    const first = drafts.find((draft) => next === "all" || draft.status === next);
    if (first) selectDraft(first);
    else { setSelectedId(null); setForm(null); setOriginal(null); }
  }

  async function readOriginal() {
    if (!selected) return;
    setReadingOriginal(true);
    setError("");
    try { setOriginal(await sourceApi.getDocument(selected.source_document_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "原文读取失败，请重试。"); }
    finally { setReadingOriginal(false); }
  }

  async function regenerate() {
    if (!selected || !form?.topic_id || !window.confirm("重新生成会覆盖这份草稿的已保存内容和未保存修改，并调用一次 AI。确定继续吗？")) return;
    setBusy(true);
    setError("");
    try {
      replaceDraft(await draftApi.generate(selected.source_document_id, form.topic_id, true, selected.revision));
      setFilter("all");
      setNotice("已重新生成，请再次核对原文和答案。");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "重新生成失败，原草稿仍保留。"); }
    finally { setBusy(false); }
  }

  function replaceDraft(next: KnowledgeDraft) {
    setDrafts((current) => current.map((draft) => draft.id === next.id ? next : draft));
    selectDraft(next);
    if (filter !== "all" && filter !== next.status) setFilter("all");
  }

  function payload(): DraftForm | null {
    if (!form || !form.topic_id || !form.title.trim() || !form.summary.trim()) return null;
    if (!form.key_points.length || form.key_points.some((item) => !item.trim())) return null;
    if (!form.quiz_items.length || form.quiz_items.some((item) => !item.question.trim() || !item.answer.trim())) return null;
    return {
      ...form,
      title: form.title.trim(),
      summary: form.summary.trim(),
      key_points: form.key_points.map((item) => item.trim()),
      quiz_items: form.quiz_items.map((item) => ({
        question: item.question.trim(),
        answer: item.answer.trim(),
      })),
    };
  }

  async function save() {
    const body = payload();
    if (!selected || !body) return;
    setBusy(true);
    setError("");
    try {
      replaceDraft(await draftApi.update(selected.id, body));
      setNotice("草稿已保存，尚未进入知识库。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "草稿保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    if (!selected || !window.confirm(`退回草稿“${selected.title}”？原资料仍会保留在待整理列表。${dirty ? "未保存的修改将丢弃。" : ""}`)) return;
    setBusy(true);
    setError("");
    try {
      replaceDraft(await draftApi.reject(selected.id, selected.revision));
      setNotice("草稿已退回，原资料未改变。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "草稿退回失败。");
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    const body = payload();
    if (!selected || !body || !window.confirm(`批准“${body.title}”并正式放入知识库？`)) return;
    setBusy(true);
    setError("");
    try {
      replaceDraft(await draftApi.approve(selected.id, body));
      setNotice("已批准入库，知识点与原资料的来源关系已保留。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "草稿批准失败。");
    } finally {
      setBusy(false);
    }
  }

  function updateKeyPoint(index: number, value: string) {
    if (!form) return;
    setForm({ ...form, key_points: form.key_points.map((item, itemIndex) => itemIndex === index ? value : item) });
  }

  function updateQuiz(index: number, value: QuizItem) {
    if (!form) return;
    setForm({ ...form, quiz_items: form.quiz_items.map((item, itemIndex) => itemIndex === index ? value : item) });
  }

  return (
    <section className={styles.review}>
      {error && <div className={styles.error} role="alert"><div><strong>这一步没有完成</strong><span>{error}</span></div><button type="button" onClick={() => setError("")} aria-label="关闭错误"><Icon name="close" size={15} /></button></div>}
      {notice && <div className={styles.notice} role="status"><Icon name="check" size={15} /><span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label="关闭提示"><Icon name="close" size={14} /></button></div>}

      <div className={styles.filterBar} aria-label="草稿状态筛选">
        {(["all", "draft", "rejected", "approved", "stale"] as Filter[]).map((value) => (
          <button type="button" key={value} disabled={busy || readingOriginal} aria-pressed={filter === value} onClick={() => changeFilter(value)}>
            {value === "all" ? "全部" : statusLabels[value]}
            <span>{value === "all" ? drafts.length : drafts.filter((draft) => draft.status === value).length}</span>
          </button>
        ))}
      </div>

      <div className={styles.workspace} aria-busy={loading || busy}>
        <aside className={styles.draftList}>
          <header><span>审核队列</span><strong>{String(visibleDrafts.length).padStart(2, "0")}</strong></header>
          {loading ? <div className={styles.loading}>正在读取草稿…</div> : visibleDrafts.length ? (
            <ol>{visibleDrafts.map((draft, index) => (
              <li key={draft.id}>
                <button type="button" disabled={busy || readingOriginal} className={draft.id === selectedId ? styles.selected : ""} onClick={() => chooseDraft(draft)}>
                  <span className={styles.number}>{String(index + 1).padStart(2, "0")}</span>
                  <span className={styles.listCopy}><strong>{draft.title}</strong><small>{draft.source_title}</small><em>{statusLabels[draft.status]} · {difficultyLabels[draft.difficulty]}</em></span>
                  <Icon name="chevron-right" size={15} />
                </button>
              </li>
            ))}</ol>
          ) : <div className={styles.empty}><Icon name="draft" size={29} /><strong>这个状态下没有草稿</strong><p>在资料收件箱选择主题后，手动生成第一份草稿。</p><Link href="/sources">前往资料收件箱</Link></div>}
        </aside>

        <div className={styles.editorPane}>
          {selected && form ? <>
            <div className={styles.sourceHead}>
              <div><span>SOURCE / {selected.source_name}</span><strong>{selected.source_title}</strong><small>AI 生成 {formatDate(selected.generated_at)} · 第 {selected.generation_count} 次</small></div>
              <span className={styles.status} data-status={selected.status}>{statusLabels[selected.status]}</span>
            </div>
            {selected.status === "stale" && <div className={styles.staleNote}><Icon name="refresh" size={18} /><div><strong>原资料已经变更</strong><p>这份草稿不能直接批准，请根据最新原文重新生成。</p></div></div>}
            {selected.source_status !== "pending" && selected.status !== "approved" && <p className={styles.staleNote}>原资料已处理或失效，这份草稿仅供查阅。</p>}
            <div className={styles.metaLine}><span>模型 {selected.model}</span><span>提示词 {selected.prompt_version}</span>{selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer">查看原文<Icon name="arrow-up-right" size={12} /></a>}</div>
            <section className={styles.original}>
              {original ? <details open><summary>核对原文 · {original.title}</summary><SourceQuality source={original} />{original.content_hash !== selected.source_content_hash && <p role="status">当前原文与这份草稿使用的版本不同，请刷新并重新生成。</p>}{original.can_supplement && <Link href={`/sources?source=${original.id}`}>前往补充正文</Link>}<SourceContent content={original.content} /></details> : <button type="button" disabled={readingOriginal || busy} onClick={readOriginal}>{readingOriginal ? "正在读取原文…" : "展开原文，核对 AI 草稿"}</button>}
            </section>

            <div className={styles.formGrid}>
              <label className={styles.full}><span>知识点名称</span><input value={form.title} maxLength={160} disabled={!editable || busy} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
              <label><span>归属主题</span><select value={form.topic_id || ""} disabled={!editable || busy} onChange={(event) => setForm({ ...form, topic_id: Number(event.target.value) })}><option value="">请选择主题</option>{categories.map((category) => <optgroup key={category.id} label={category.name}>{topics.filter((topic) => topic.category_id === category.id).map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</optgroup>)}</select></label>
              <label><span>难度</span><select value={form.difficulty} disabled={!editable || busy} onChange={(event) => setForm({ ...form, difficulty: event.target.value as Difficulty })}>{(Object.keys(difficultyLabels) as Difficulty[]).map((value) => <option key={value} value={value}>{difficultyLabels[value]}</option>)}</select></label>
              <label className={styles.full}><span>摘要</span><textarea aria-label="摘要" rows={6} maxLength={6000} value={form.summary} disabled={!editable || busy} onChange={(event) => setForm({ ...form, summary: event.target.value })} /></label>
            </div>

            <section className={styles.repeatSection}>
              <div className={styles.sectionTitle}><div><span>KEY POINTS</span><strong>核心要点</strong></div>{editable && form.key_points.length < 8 && <button type="button" disabled={busy} onClick={() => setForm({ ...form, key_points: [...form.key_points, ""] })}><Icon name="plus" size={13} />添加要点</button>}</div>
              <ol className={styles.keyPoints}>{form.key_points.map((item, index) => <li key={index}><span>{String(index + 1).padStart(2, "0")}</span><input value={item} maxLength={300} disabled={!editable || busy} onChange={(event) => updateKeyPoint(index, event.target.value)} />{editable && form.key_points.length > 1 && <button type="button" disabled={busy} aria-label={`删除第 ${index + 1} 个要点`} onClick={() => setForm({ ...form, key_points: form.key_points.filter((_, itemIndex) => itemIndex !== index) })}><Icon name="close" size={13} /></button>}</li>)}</ol>
            </section>

            <section className={styles.repeatSection}>
              <div className={styles.sectionTitle}><div><span>QUIZ</span><strong>测试题与标准答案</strong></div>{editable && form.quiz_items.length < 5 && <button type="button" disabled={busy} onClick={() => setForm({ ...form, quiz_items: [...form.quiz_items, { question: "", answer: "" }] })}><Icon name="plus" size={13} />添加题目</button>}</div>
              <div className={styles.quizList}>{form.quiz_items.map((item, index) => <article key={index}><div className={styles.quizNumber}>Q{index + 1}</div><label><span>问题</span><input value={item.question} maxLength={500} disabled={!editable || busy} onChange={(event) => updateQuiz(index, { ...item, question: event.target.value })} /></label><label><span>标准答案</span><textarea rows={3} maxLength={2000} value={item.answer} disabled={!editable || busy} onChange={(event) => updateQuiz(index, { ...item, answer: event.target.value })} /></label>{editable && form.quiz_items.length > 1 && <button disabled={busy} className={styles.removeQuiz} type="button" onClick={() => setForm({ ...form, quiz_items: form.quiz_items.filter((_, itemIndex) => itemIndex !== index) })}>删除这道题</button>}</article>)}</div>
            </section>

            <div className={styles.actions}>
              {selected.status === "approved" ? selected.knowledge_point_id ? <Link className={styles.knowledgeLink} href={`/knowledge/detail?point=${selected.knowledge_point_id}`}><Icon name="check" size={15} />查看已入库知识点</Link> : <span>对应知识点已删除，草稿记录仍保留。</span> : editable ? <><button type="button" className={styles.saveButton} disabled={busy || !payload()} onClick={save}>{busy ? "处理中…" : "保存草稿"}</button><button type="button" className={styles.approveButton} disabled={busy || !payload()} onClick={approve}><Icon name="check" size={15} />批准入库</button><button type="button" className={styles.rejectButton} disabled={busy} onClick={reject}>退回草稿</button></> : null}
              {selected.status !== "approved" && selected.source_status === "pending" && <button type="button" className={styles.rejectButton} disabled={busy || !form.topic_id} onClick={regenerate}>重新生成</button>}
            </div>
          </> : <div className={styles.detailEmpty}><Icon name="draft" size={32} /><strong>选择一份草稿</strong><p>逐条核对 AI 摘要和答案，再决定是否入库。</p></div>}
        </div>
      </div>
      <div className={styles.footnote}><span><Icon name="leaf" size={14} />AI 只起草，批准权始终在你手里。</span><span>REVIEW BEFORE YOU KEEP.</span></div>
    </section>
  );
}
