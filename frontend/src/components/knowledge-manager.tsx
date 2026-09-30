"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/icon";
import { knowledgeApi } from "@/lib/api";
import type { Category, KnowledgePoint, Topic } from "@/lib/types";

import styles from "./knowledge-manager.module.css";

type Draft = { id?: number; name: string; description: string };
type Editor = "category" | "topic" | "point" | null;
type NamedEntity = { id: number; name: string; description: string | null };
const emptyDraft: Draft = { name: "", description: "" };

function selectionFromUrl(url: URL, categories: Category[], topics: Topic[], fallbackCategoryId: number | null) {
  const requestedCategoryId = Number(url.searchParams.get("category"));
  const requestedTopicId = Number(url.searchParams.get("topic"));
  const requestedTopic = topics.find((item) => item.id === requestedTopicId);
  const categoryId = categories.some((item) => item.id === requestedCategoryId)
    ? requestedCategoryId : requestedTopic?.category_id ?? fallbackCategoryId;
  const categoryTopics = topics.filter((item) => item.category_id === categoryId);
  const topicId = categoryTopics.some((item) => item.id === requestedTopicId)
    ? requestedTopicId : (categoryTopics[0]?.id ?? null);
  return { categoryId, topicId };
}

function pointFromUrl(url: URL) {
  return Number(url.searchParams.get("point") || url.hash.match(/^#knowledge-point-(\d+)$/)?.[1]);
}

export function KnowledgeManager() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [knowledgePoints, setKnowledgePoints] = useState<KnowledgePoint[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const [activeTopicId, setActiveTopicId] = useState<number | null>(null);
  const [categoryDraft, setCategoryDraft] = useState<Draft>(emptyDraft);
  const [topicDraft, setTopicDraft] = useState<Draft>(emptyDraft);
  const [pointDraft, setPointDraft] = useState<Draft>(emptyDraft);
  const [editor, setEditor] = useState<Editor>(null);
  const [search, setSearch] = useState("");
  const [notesOnly, setNotesOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const pendingAnchor = useRef<string | null>(null);

  const focusAnchor = useCallback((id: string) => {
    pendingAnchor.current = id;
    window.requestAnimationFrame(() => {
      const element = document.getElementById(id);
      if (!element || pendingAnchor.current !== id) return;
      element.scrollIntoView({ block: "center" });
      element.focus({ preventScroll: true });
      pendingAnchor.current = null;
    });
  }, []);

  const loadAll = useCallback(async () => {
    const [nextCategories, nextTopics, nextPoints] = await Promise.all([
      knowledgeApi.listCategories(), knowledgeApi.listTopics(), knowledgeApi.listKnowledgePoints(),
    ]);
    setCategories(nextCategories);
    setTopics(nextTopics);
    setKnowledgePoints(nextPoints);
    setActiveCategoryId((current) => current && nextCategories.some((item) => item.id === current)
      ? current : (nextCategories[0]?.id ?? null));
    setUnavailable(false);
    return { categories: nextCategories, topics: nextTopics, points: nextPoints };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([knowledgeApi.listCategories(), knowledgeApi.listTopics(), knowledgeApi.listKnowledgePoints()])
      .then(([nextCategories, nextTopics, nextPoints]) => {
        if (cancelled) return;
        setCategories(nextCategories);
        setTopics(nextTopics);
        setKnowledgePoints(nextPoints);
        const url = new URL(window.location.href);
        const selection = selectionFromUrl(url, nextCategories, nextTopics, nextCategories[0]?.id ?? null);
        setActiveCategoryId(selection.categoryId);
        setActiveTopicId(selection.topicId);
        if (url.searchParams.get("new") === "category" || url.hash === "#new-category") setEditor("category");
        if (url.hash === "#knowledge-search") focusAnchor("knowledge-search");
        const pointId = pointFromUrl(url);
        if (nextPoints.some((point) => point.id === pointId && point.topic_id === selection.topicId)) focusAnchor(`knowledge-point-${pointId}`);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(cause instanceof Error ? cause.message : "无法读取知识结构");
        setUnavailable(true);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [focusAnchor]);

  const activeCategory = categories.find((item) => item.id === activeCategoryId);
  const visibleTopics = useMemo(() => topics.filter((topic) => topic.category_id === activeCategoryId), [topics, activeCategoryId]);
  const selectedTopicId = activeTopicId && visibleTopics.some((item) => item.id === activeTopicId)
    ? activeTopicId : (visibleTopics[0]?.id ?? null);
  const selectedTopic = visibleTopics.find((item) => item.id === selectedTopicId);
  const visiblePoints = useMemo(() => knowledgePoints.filter((point) => point.topic_id === selectedTopicId), [knowledgePoints, selectedTopicId]);
  const filteredPoints = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return visiblePoints.filter((point) => (!notesOnly || Boolean(point.description?.trim())) &&
      (!query || `${point.name} ${point.description ?? ""} ${point.summary ?? ""} ${(point.key_points ?? []).join(" ")}`.toLocaleLowerCase().includes(query)));
  }, [visiblePoints, search, notesOnly]);

  useEffect(() => {
    if (loading || !pendingAnchor.current) return;
    const element = document.getElementById(pendingAnchor.current);
    if (!element) return;
    element.scrollIntoView({ block: "center" });
    element.focus({ preventScroll: true });
    pendingAnchor.current = null;
  }, [loading, selectedTopicId, filteredPoints]);

  useEffect(() => {
    const applyLocation = (url: URL, applyHierarchy: boolean) => {
      // Action links should not re-apply a domain left over in the current URL.
      if (url.hash === "#new-category" || (!url.hash && url.searchParams.get("new") === "category")) {
        if (unavailable) return;
        setCategoryDraft(emptyDraft);
        setEditor("category");
        return;
      }
      if (url.hash === "#knowledge-search") {
        focusAnchor("knowledge-search");
        return;
      }
      let topicId = selectedTopicId;
      if (applyHierarchy && (url.searchParams.has("category") || url.searchParams.has("topic"))) {
        const selection = selectionFromUrl(url, categories, topics, activeCategoryId);
        setActiveCategoryId(selection.categoryId);
        setActiveTopicId(selection.topicId);
        setEditor(null);
        setSearch("");
        setNotesOnly(false);
        topicId = selection.topicId;
      }
      const pointId = pointFromUrl(url);
      if (knowledgePoints.some((point) => point.id === pointId && point.topic_id === topicId)) focusAnchor(`knowledge-point-${pointId}`);
    };
    const onHashChange = () => applyLocation(new URL(window.location.href), false);
    const onPopState = () => applyLocation(new URL(window.location.href), true);
    const followLocalAction = (event: MouseEvent) => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(anchor instanceof HTMLAnchorElement)) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin === window.location.origin && url.pathname === window.location.pathname) applyLocation(url, true);
    };
    window.addEventListener("hashchange", onHashChange);
    window.addEventListener("popstate", onPopState);
    document.addEventListener("click", followLocalAction);
    return () => {
      window.removeEventListener("hashchange", onHashChange);
      window.removeEventListener("popstate", onPopState);
      document.removeEventListener("click", followLocalAction);
    };
  }, [activeCategoryId, categories, focusAnchor, knowledgePoints, selectedTopicId, topics, unavailable]);

  async function retryConnection() {
    setLoading(true);
    setError(null);
    try {
      const loaded = await loadAll();
      const url = new URL(window.location.href);
      const selection = selectionFromUrl(url, loaded.categories, loaded.topics, loaded.categories[0]?.id ?? null);
      setActiveCategoryId(selection.categoryId);
      setActiveTopicId(selection.topicId);
      if (url.searchParams.get("new") === "category" || url.hash === "#new-category") setEditor("category");
      if (url.hash === "#knowledge-search") focusAnchor("knowledge-search");
      const pointId = pointFromUrl(url);
      if (loaded.points.some((point) => point.id === pointId && point.topic_id === selection.topicId)) focusAnchor(`knowledge-point-${pointId}`);
    } catch (cause) {
      setUnavailable(true);
      setError(cause instanceof Error ? cause.message : "无法读取知识结构");
    } finally {
      setLoading(false);
    }
  }

  async function runMutation(action: () => Promise<unknown>, reset: () => void, message: string) {
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      await action();
      reset();
      await loadAll();
      setNotice(message);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  function submitCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = { name: categoryDraft.name.trim(), description: categoryDraft.description.trim() };
    if (!payload.name) return;
    void runMutation(async () => {
      if (categoryDraft.id) return knowledgeApi.updateCategory(categoryDraft.id, payload);
      const created = await knowledgeApi.createCategory(payload);
      setActiveCategoryId(created.id);
      setActiveTopicId(null);
    }, () => { setCategoryDraft(emptyDraft); setEditor(null); }, categoryDraft.id ? "领域已更新" : "新领域已加入你的知识库");
  }

  function submitTopic(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeCategoryId || !topicDraft.name.trim()) return;
    const payload = { category_id: activeCategoryId, name: topicDraft.name.trim(), description: topicDraft.description.trim() };
    void runMutation(async () => {
      if (topicDraft.id) return knowledgeApi.updateTopic(topicDraft.id, payload);
      const created = await knowledgeApi.createTopic(payload);
      setActiveTopicId(created.id);
      setSearch("");
      setNotesOnly(false);
    }, () => { setTopicDraft(emptyDraft); setEditor(null); }, topicDraft.id ? "主题已更新" : "主题已创建，可以开始记录了");
  }

  function submitPoint(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTopicId || !pointDraft.name.trim()) return;
    const payload = { topic_id: selectedTopicId, name: pointDraft.name.trim(), description: pointDraft.description.trim() };
    void runMutation(() => pointDraft.id
      ? knowledgeApi.updateKnowledgePoint(pointDraft.id, payload) : knowledgeApi.createKnowledgePoint(payload),
    () => { setPointDraft(emptyDraft); setEditor(null); setSearch(""); setNotesOnly(false); },
    pointDraft.id ? "知识点已更新" : "又积累了一点新知识");
  }

  function confirmDelete(label: string, action: () => Promise<unknown>, hasChildren = true) {
    const consequence = hasChildren ? "其下级内容也会一起删除。" : "该操作无法撤销。";
    if (!window.confirm(`确定删除“${label}”吗？${consequence}`)) return;
    void runMutation(action, () => setEditor(null), "已删除所选内容");
  }

  function openEditor(next: Exclude<Editor, null>, item?: NamedEntity) {
    const draft = item ? { id: item.id, name: item.name, description: item.description ?? "" } : emptyDraft;
    if (next === "category") setCategoryDraft(draft);
    if (next === "topic") setTopicDraft(draft);
    if (next === "point") setPointDraft(draft);
    setEditor(next);
    setNotice("");
  }

  function selectCategory(id: number) {
    setActiveCategoryId(id);
    setActiveTopicId(null);
    setEditor(null);
    setSearch("");
    setNotesOnly(false);
  }

  return (
    <div className={styles.manager}>
      {error && <div className={styles.error} role="alert"><div><strong>暂时没有完成</strong><span>{error}</span></div><button type="button" onClick={() => setError(null)} aria-label="关闭错误提示"><Icon name="close" size={18} /></button></div>}
      <div className={styles.overview}>
        <div className={styles.overviewLabel}><span className={styles.liveDot} />个人知识空间<span className={styles.total}>{loading ? "正在读取…" : unavailable ? "暂时无法读取" : `${categories.length} 个领域 · ${knowledgePoints.length} 个知识点`}</span></div>
        <button type="button" className={styles.secondaryButton} id="new-category" disabled={busy || loading || unavailable} onClick={() => openEditor("category")}><Icon name="plus" size={16} />新建领域</button>
      </div>
      <div className={styles.workspace} aria-busy={busy || loading}>
        <aside className={styles.categoryRail} aria-label="知识领域">
          <div className={styles.railHeading}><span>我的领域</span><span>{unavailable || loading ? "—" : String(categories.length).padStart(2, "0")}</span></div>
          {loading ? <p className={styles.railEmpty}>正在整理你的知识库…</p> : unavailable ? <p className={styles.railEmpty}>等待连接知识库</p> : categories.length ? (
            <ul className={styles.categoryList}>{categories.map((category, index) => (
              <li key={category.id} className={category.id === activeCategoryId ? styles.categorySelected : ""}>
                <button type="button" className={styles.categorySelect} aria-pressed={category.id === activeCategoryId} disabled={busy} onClick={() => selectCategory(category.id)}>
                  <span className={styles.categoryMark} data-tone={index % 3}><Icon name="folder" size={17} /></span>
                  <span className={styles.categoryName}>{category.name}<small>{topics.filter((topic) => topic.category_id === category.id).length} 个主题</small></span><Icon name="chevron-right" size={15} />
                </button>
                <div className={styles.categoryActions}>
                  <button type="button" title="编辑领域" aria-label={`编辑领域“${category.name}”`} disabled={busy} onClick={() => openEditor("category", category)}><Icon name="edit" size={14} /></button>
                  <button type="button" className={styles.deleteButton} title="删除领域" aria-label={`删除领域“${category.name}”`} disabled={busy} onClick={() => confirmDelete(category.name, () => knowledgeApi.deleteCategory(category.id))}><Icon name="trash" size={14} /></button>
                </div>
              </li>
            ))}</ul>
          ) : <p className={styles.railEmpty}>还没有领域。<br />给你的好奇心留个位置。</p>}
          {editor === "category" && <EditorForm label="领域" draft={categoryDraft} disabled={busy || loading || unavailable} onChange={setCategoryDraft} onSubmit={submitCategory} onCancel={() => setEditor(null)} />}
          <div className={styles.railNote}><Icon name="leaf" size={18} /><p>知识不用一口气整理好。<br />每天留下一点，就很好。</p></div>
        </aside>
        <section className={styles.content} aria-label="主题和知识点">
          {loading ? (
            <div className={styles.loadingState} role="status"><span className={styles.skeletonTitle} /><span className={styles.skeletonLine} /><span className={styles.skeletonBlock} /><p>正在读取你的知识库…</p></div>
          ) : unavailable ? (
            <div className={styles.unavailableState} role="status"><Icon name="refresh" size={28} /><h3>知识库暂时没连上</h3><p>暂时无法读取你的知识内容，请稍后重试。</p><button type="button" className={styles.secondaryButton} onClick={() => void retryConnection()}><Icon name="refresh" size={15} />重新连接</button></div>
          ) : !activeCategory ? (
            <EmptyWorkspace step="01" title="从一个感兴趣的领域开始" description="编程、摄影，或最近想读懂的任何事。先给它起个名字，再慢慢填满。" action="创建第一个领域" onAction={() => openEditor("category")} disabled={busy} />
          ) : <>
            <header className={styles.contentHeading}><div><span className={styles.eyebrow}>YOUR COLLECTION</span><h2>{activeCategory.name}</h2><p>{activeCategory.description || "把零散的灵感，整理成自己的知识。"}</p></div><span className={styles.topicCount}><Icon name="layers" size={15} />{visibleTopics.length} 个主题</span></header>
            <div className={styles.topicBar}>
              <div className={styles.topicTabs} aria-label="选择主题">
                {visibleTopics.map((topic) => <button type="button" key={topic.id} className={topic.id === selectedTopicId ? styles.topicActive : ""} aria-pressed={topic.id === selectedTopicId} disabled={busy} onClick={() => { setActiveTopicId(topic.id); setEditor(null); setSearch(""); setNotesOnly(false); }}>{topic.name}<span>{knowledgePoints.filter((point) => point.topic_id === topic.id).length}</span></button>)}
                {!visibleTopics.length && <span className={styles.noTopics}>主题，让知识更有条理</span>}
              </div>
              <button type="button" className={styles.addTopic} disabled={busy} onClick={() => openEditor("topic")}><Icon name="plus" size={15} /><span>新建主题</span></button>
            </div>
            {editor === "topic" && <div className={styles.mainEditor}><EditorForm label="主题" draft={topicDraft} disabled={busy || !activeCategoryId} onChange={setTopicDraft} onSubmit={submitTopic} onCancel={() => setEditor(null)} /></div>}
            {!selectedTopic ? (
              <EmptyWorkspace step="02" title="把领域拆成小主题" description={`在“${activeCategory.name}”里，你想先学哪一部分？一个清晰的小主题，会让开始更轻松。`} action="添加第一个主题" onAction={() => openEditor("topic")} disabled={busy} />
            ) : <>
              <div className={styles.topicDetails}><div className={styles.path}><span>{activeCategory.name}</span><Icon name="chevron-right" size={13} /><strong>{selectedTopic.name}</strong></div><div className={styles.textActions}><button type="button" disabled={busy} onClick={() => openEditor("topic", selectedTopic)}>编辑主题</button><span>/</span><button type="button" className={styles.deleteButton} disabled={busy} onClick={() => confirmDelete(selectedTopic.name, () => knowledgeApi.deleteTopic(selectedTopic.id))}>删除</button></div></div>
              {selectedTopic.description && <p className={styles.topicDescription}>{selectedTopic.description}</p>}
              <div className={styles.listToolbar}>
                <label className={styles.search}><Icon name="search" size={17} /><input id="knowledge-search" aria-label="搜索当前主题的知识点" placeholder="搜索这个主题里的知识…" value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button type="button" aria-label="清除搜索" onClick={() => setSearch("")}><Icon name="close" size={15} /></button>}</label>
                <button type="button" className={styles.primaryButton} disabled={busy} onClick={() => openEditor("point")}><Icon name="plus" size={16} />记录知识点</button>
              </div>
              <div className={styles.filterBar}><div className={styles.filters}><button type="button" aria-pressed={!notesOnly} className={!notesOnly ? styles.filterActive : ""} onClick={() => setNotesOnly(false)}>全部知识点 <span>{visiblePoints.length}</span></button><button type="button" aria-pressed={notesOnly} className={notesOnly ? styles.filterActive : ""} onClick={() => setNotesOnly(true)}>有笔记</button></div><span>{filteredPoints.length} 条内容</span></div>
              {editor === "point" && <div className={styles.pointEditor}><EditorForm label="知识点" draft={pointDraft} disabled={busy || !selectedTopicId} onChange={setPointDraft} onSubmit={submitPoint} onCancel={() => setEditor(null)} /></div>}
              {!visiblePoints.length ? (
                <EmptyWorkspace step="03" title="把刚学会的，留在这里" description="一个概念、一个解题方法，或一句让你恍然大悟的话。写下来，下一次就能找到它。" action="记录第一个知识点" onAction={() => openEditor("point")} disabled={busy} />
              ) : !filteredPoints.length ? (
                <div className={styles.noResults}><Icon name="search" size={25} /><h3>这次没有找到匹配的知识点</h3><p>换个关键词，或试试查看全部内容。</p><button type="button" className={styles.secondaryButton} onClick={() => { setSearch(""); setNotesOnly(false); }}>清除筛选</button></div>
              ) : <ul className={styles.pointList}>{filteredPoints.map((point, index) => (
                <li key={point.id} id={`knowledge-point-${point.id}`} tabIndex={-1}>
                  <span className={styles.pointNumber}>{String(index + 1).padStart(2, "0")}</span>
                  <div className={styles.pointBody}><h3><Link href={`/knowledge/detail?point=${point.id}`}>{point.name}</Link></h3>{point.summary || point.description ? <p>{point.summary || point.description}</p> : <button type="button" className={styles.addNote} disabled={busy} onClick={() => openEditor("point", point)}>添加一点自己的理解 <Icon name="plus" size={12} /></button>}<span className={styles.pointMeta}><Icon name="book" size={12} />{point.description?.trim() ? "已记录笔记" : "待补充笔记"} · {point.quiz_items?.length ?? 0} 道练习题</span><Link className={styles.addNote} href={`/knowledge/detail?point=${point.id}`}>阅读与练习 <Icon name="arrow-right" size={12} /></Link></div>
                  <div className={styles.pointActions}><button type="button" title="编辑知识点" aria-label={`编辑知识点“${point.name}”`} disabled={busy} onClick={() => openEditor("point", point)}><Icon name="edit" size={16} /></button><button type="button" className={styles.deleteButton} title="删除知识点" aria-label={`删除知识点“${point.name}”`} disabled={busy} onClick={() => confirmDelete(point.name, () => knowledgeApi.deleteKnowledgePoint(point.id), false)}><Icon name="trash" size={16} /></button></div>
                </li>
              ))}</ul>}
            </>}
          </>}
        </section>
      </div>
      <div className={styles.bottomNote}><span>领域 <Icon name="chevron-right" size={12} />主题 <Icon name="chevron-right" size={12} />知识点</span><span role="status">{busy ? "正在保存…" : unavailable ? "等待连接知识库" : notice || "每一点积累，都算数。"}</span></div>
    </div>
  );
}

function EmptyWorkspace({ step, title, description, action, onAction, disabled }: {
  step: string; title: string; description: string; action: string; onAction: () => void; disabled: boolean;
}) {
  return <div className={styles.emptyWorkspace}><div className={styles.emptySketch} aria-hidden="true"><span className={styles.sketchBack} /><span className={styles.sketchFront}><Icon name="leaf" size={29} /><i /><i /></span><span className={styles.sketchPlus}>+</span></div><span className={styles.emptyStep}>STEP {step} / 03</span><h3>{title}</h3><p>{description}</p><button type="button" className={styles.primaryButton} disabled={disabled} onClick={onAction}><Icon name="plus" size={16} />{action}</button></div>;
}

function EditorForm({ label, draft, disabled, onChange, onSubmit, onCancel }: {
  label: string; draft: Draft; disabled: boolean; onChange: (draft: Draft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void;
}) {
  return (
    <form className={styles.editor} onSubmit={onSubmit}>
      <div className={styles.editorHeading}><strong>{draft.id ? "编辑" : "新建"}{label}</strong><button type="button" disabled={disabled} onClick={onCancel} aria-label={`关闭${label}编辑器`}><Icon name="close" size={16} /></button></div>
      <label><span>{label}名称</span><input autoFocus value={draft.name} onChange={(event) => onChange({ ...draft, name: event.target.value })} placeholder={label === "领域" ? "比如：设计、编程、生活" : `给这个${label}起个名字`} disabled={disabled} maxLength={label === "知识点" ? 160 : 120} required /></label>
      <label><span>{label === "知识点" ? "我的理解" : "简短说明"}<small>可选</small></span><textarea value={draft.description} onChange={(event) => onChange({ ...draft, description: event.target.value })} placeholder={label === "知识点" ? "试着用自己的话，解释这个知识点…" : "这里会收集什么内容？"} disabled={disabled} rows={label === "知识点" ? 4 : 2} /></label>
      <div className={styles.editorActions}><button className={styles.primaryButton} type="submit" disabled={disabled || !draft.name.trim()}>{disabled ? "保存中…" : draft.id ? "保存修改" : `添加${label}`}<Icon name="arrow-right" size={14} /></button><button type="button" className={styles.cancelButton} disabled={disabled} onClick={onCancel}>取消</button></div>
    </form>
  );
}
