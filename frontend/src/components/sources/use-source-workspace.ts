"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useUnsavedChanges } from "@/components/use-unsaved-changes";
import { draftApi, knowledgeApi, sourceApi } from "@/lib/api";
import { emptySourceFilters, filterSources, preferredSourceTopic, rememberSource, sourceStatusOptions, type SourceFilters } from "@/lib/source-workspace";
import type { Category, KnowledgeDraft, SourceDocument, SourceStatus, Topic } from "@/lib/types";

type InboxData = { documents: SourceDocument[]; categories: Category[]; topics: Topic[]; drafts: KnowledgeDraft[] };
type Operation = "sync" | "score-batch" | "score-one" | "accept" | "generate" | "ignore";
export type SourceEditor = {
  categoryId: number | "";
  topicId: number | "";
  name: string;
  description: string;
  descriptionMode: "preview" | "edit";
  manualOpen: boolean;
};

function editorFor(document: SourceDocument | null, categories: Category[], topics: Topic[]): SourceEditor {
  return { ...preferredSourceTopic(document, categories, topics), name: document?.title.slice(0, 160) ?? "",
    description: document?.content ?? "", descriptionMode: "preview", manualOpen: false };
}

async function fetchInbox(status: SourceStatus): Promise<InboxData> {
  const [documents, categories, topics, drafts] = await Promise.all([
    sourceApi.listDocuments(status), knowledgeApi.listCategories(), knowledgeApi.listTopics(), draftApi.list(),
  ]);
  return { documents, categories, topics, drafts };
}

export function useSourceWorkspace() {
  const router = useRouter();
  const [data, setData] = useState<InboxData>({ documents: [], categories: [], topics: [], drafts: [] });
  const [status, setStatus] = useState<SourceStatus>("pending");
  const [filters, setFilters] = useState(emptySourceFilters);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editor, setEditor] = useState<SourceEditor>(() => editorFor(null, [], []));
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [contentLocked, setContentLocked] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const requestId = useRef(0);
  const mounted = useRef(true);
  const working = loading || operation !== null;
  const busy = working || contentLocked;
  const selected = data.documents.find((document) => document.id === selectedId) ?? null;
  const manualDirty = selected !== null && (editor.name !== selected.title.slice(0, 160) || editor.description !== selected.content);
  const existingDraft = data.drafts.find((draft) => draft.source_document_id === selectedId && draft.status !== "approved");
  const visibleDocuments = useMemo(() => filterSources(data.documents, filters), [data.documents, filters]);
  useUnsavedChanges(manualDirty && !contentLocked);

  const applySelection = useCallback((document: SourceDocument | null, categories: Category[], topics: Topic[], nextStatus: SourceStatus) => {
    setSelectedId(document?.id ?? null);
    setEditor(editorFor(document, categories, topics));
    rememberSource(nextStatus, document?.id ?? null);
  }, []);

  const applyInbox = useCallback((next: InboxData, nextStatus: SourceStatus, preferredId: number | null, nextFilters: SourceFilters) => {
    const visible = filterSources(next.documents, nextFilters);
    const document = visible.find((item) => item.id === preferredId) ?? visible[0] ?? null;
    setData(next); setStatus(nextStatus); setFilters(nextFilters);
    applySelection(document, next.categories, next.topics, nextStatus);
  }, [applySelection]);

  const load = useCallback(async (nextStatus: SourceStatus, preferredId: number | null, nextFilters: SourceFilters) => {
    const request = ++requestId.current;
    setLoading(true); setLoadFailed(false); setError("");
    setStatus(nextStatus); setFilters(nextFilters);
    rememberSource(nextStatus, preferredId);
    try {
      const next = await fetchInbox(nextStatus);
      if (request !== requestId.current) return;
      applyInbox(next, nextStatus, preferredId, nextFilters);
    } catch (reason) {
      if (request !== requestId.current) return;
      // Keep editor values in memory, but never expose stale actions after a failed read.
      setLoadFailed(true);
      setError(reason instanceof Error ? reason.message : "资料读取失败，请稍后重试。");
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  }, [applyInbox]);

  useEffect(() => {
    mounted.current = true;
    const params = new URLSearchParams(window.location.search);
    const initialStatus = sourceStatusOptions.find((option) => option.value === params.get("status"))?.value ?? "pending";
    const requestedId = Number(params.get("source"));
    const request = ++requestId.current;
    fetchInbox(initialStatus).then((next) => {
      if (request === requestId.current) applyInbox(next, initialStatus, requestedId > 0 ? requestedId : null, emptySourceFilters);
    }).catch((reason: unknown) => {
      if (request !== requestId.current) return;
      setStatus(initialStatus); setLoadFailed(true);
      setError(reason instanceof Error ? reason.message : "资料读取失败，请稍后重试。");
    }).finally(() => { if (request === requestId.current) setLoading(false); });
    return () => { mounted.current = false; requestId.current += 1; };
  }, [applyInbox]);

  function confirmDiscard() {
    return !manualDirty || window.confirm("手动整理有尚未保存的内容，确定放弃这些编辑吗？");
  }

  function selectDocument(document: SourceDocument) {
    if (busy || loadFailed || document.id === selectedId || !confirmDiscard()) return;
    applySelection(document, data.categories, data.topics, status);
    setError(""); setNotice("");
  }

  function changeFilters(next: SourceFilters) {
    if (busy || loadFailed) return;
    const visible = filterSources(data.documents, next);
    const document = visible.find((item) => item.id === selectedId) ?? visible[0] ?? null;
    if (document?.id !== selected?.id && !confirmDiscard()) return;
    setFilters(next);
    if (document?.id !== selected?.id) applySelection(document, data.categories, data.topics, status);
  }

  function changeStatus(next: SourceStatus) {
    if (busy || next === status || !confirmDiscard()) return;
    setNotice("");
    void load(next, null, emptySourceFilters);
  }

  function retryLoad() {
    if (busy || !confirmDiscard()) return;
    const requestedId = Number(new URLSearchParams(window.location.search).get("source"));
    void load(status, requestedId > 0 ? requestedId : null, filters);
  }

  function patchEditor(patch: Partial<SourceEditor>) {
    setEditor((current) => ({ ...current, ...patch }));
  }

  function changeCategory(categoryId: number) {
    patchEditor({ categoryId, topicId: data.topics.find((topic) => topic.category_id === categoryId)?.id ?? "" });
  }

  function applySupplement(next: SourceDocument) {
    const changed = next.content_hash !== selected?.content_hash;
    setData((current) => ({ ...current,
      documents: current.documents.map((item) => item.id === next.id ? next : item),
      drafts: changed ? current.drafts.map((draft) => draft.source_document_id === next.id ? { ...draft, status: "stale" } : draft) : current.drafts,
    }));
    setEditor((current) => ({ ...current,
      name: current.name === selected?.title.slice(0, 160) ? next.title.slice(0, 160) : current.name,
      description: current.description === selected?.content ? next.content : current.description,
    }));
    setNotice(changed ? "正文已更新。已有草稿文字仍保留，请重新生成并审核；尚未入库。" : "正文来源设置已保存，内容未变更。");
  }

  async function runAction(name: Operation, action: () => Promise<void>) {
    if (busy || loadFailed) return;
    setOperation(name); setError(""); setNotice("");
    try { await action(); }
    catch (reason) { if (mounted.current) setError(reason instanceof Error ? reason.message : "这一步没有完成，请稍后重试。"); }
    finally { if (mounted.current) setOperation(null); }
  }

  async function syncNotebook() {
    if (!confirmDiscard()) return;
    await runAction("sync", async () => {
      const result = await sourceApi.syncNotebook();
      if (!mounted.current) return;
      setNotice(`同步完成：新增 ${result.created}，更新 ${result.updated}，未变化 ${result.unchanged}，失效 ${result.stale}。`);
      await load("pending", selectedId, status === "pending" ? filters : emptySourceFilters);
    });
  }

  async function analyzePending() {
    if (!confirmDiscard()) return;
    await runAction("score-batch", async () => {
      const result = await sourceApi.scorePending();
      if (!mounted.current) return;
      setNotice(`分析完成：成功 ${result.scored}，相关 ${result.passed}，Embedding ${result.embedding}，本地关键词 ${result.keyword}${result.failed ? `，失败 ${result.failed}` : ""}。`);
      await load(status, selectedId, filters);
    });
  }

  async function analyzeSelected() {
    if (!selected) return;
    await runAction("score-one", async () => {
      const scored = await sourceApi.scoreDocument(selected.id);
      if (!mounted.current) return;
      setData((current) => ({ ...current, documents: current.documents.map((item) => item.id === scored.id ? scored : item) }));
      patchEditor(preferredSourceTopic(scored, data.categories, data.topics));
      setNotice(`“${scored.title}”已完成相关性分析。`);
    });
  }

  async function accept() {
    const topicId = editor.topicId;
    if (!selected || !topicId || !editor.name.trim() || busy || loadFailed ||
      !window.confirm(`确认把“${editor.name.trim()}”直接放进知识库？这不会生成 AI 草稿或练习题。`)) return;
    await runAction("accept", async () => {
      await sourceApi.acceptDocument(selected.id, { topic_id: topicId, name: editor.name, description: editor.description });
      if (!mounted.current) return;
      setNotice(`“${editor.name.trim()}”已经进入知识库。`);
      await load(status, selectedId, filters);
    });
  }

  async function generateDraft() {
    if (!selected || busy || loadFailed || (!editor.topicId && !existingDraft)) return;
    if (manualDirty && !window.confirm("手动编辑还没有入库。AI 只会使用资料正文，继续前往草稿流程并放弃手动编辑吗？")) return;
    if (existingDraft) { router.push(`/drafts?draft=${existingDraft.id}`); return; }
    const topicId = editor.topicId;
    if (!topicId) return;
    await runAction("generate", async () => {
      const draft = await draftApi.generate(selected.id, topicId);
      if (mounted.current) router.push(`/drafts?draft=${draft.id}`);
    });
  }

  async function ignoreSelected() {
    if (!selected || busy || loadFailed || !window.confirm(`暂时忽略“${selected.title}”？之后仍可在“已忽略”中查看。${manualDirty ? "未保存的手动编辑将被放弃。" : ""}`)) return;
    await runAction("ignore", async () => {
      await sourceApi.ignoreDocument(selected.id);
      if (!mounted.current) return;
      setNotice("这条资料已移到“已忽略”。");
      await load(status, selectedId, filters);
    });
  }

  return { ...data, status, filters, selected, visibleDocuments, editor, existingDraft, manualDirty,
    loading, loadFailed, operation, working, busy, error, notice, setError, setNotice, setContentLocked,
    selectDocument, changeFilters, changeStatus, retryLoad, patchEditor, changeCategory, applySupplement,
    syncNotebook, analyzePending, analyzeSelected, accept, generateDraft, ignoreSelected };
}
