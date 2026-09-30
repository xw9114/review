"use client";

import { useState } from "react";
import { SourceContent } from "@/components/source-content";
import { SourceQuality } from "@/components/source-quality";
import { useUnsavedChanges } from "@/components/use-unsaved-changes";
import { sourceApi } from "@/lib/api";
import type { SourceCollectedContent, SourceDocument } from "@/lib/types";
import styles from "./source-supplement.module.css";

type Props = {
  source: SourceDocument;
  disabled: boolean;
  onLockChange: (locked: boolean) => void;
  onApplied: (source: SourceDocument) => void;
};

export function SourceSupplement({ source, disabled, onLockChange, onApplied }: Props) {
  const [editing, setEditing] = useState(false);
  const [candidate, setCandidate] = useState("");
  const [revision, setRevision] = useState(source.content_revision);
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [collected, setCollected] = useState<SourceCollectedContent | null>(null);
  const dirty = editing && candidate !== source.content;
  useUnsavedChanges(dirty);

  function openEditor(content: string, expectedRevision: number, showPreview = false) {
    setCandidate(content);
    setRevision(expectedRevision);
    setPreview(showPreview);
    setEditing(true);
    onLockChange(true);
  }

  function closeEditor() {
    if (dirty && !window.confirm("放弃尚未应用的候选正文？当前资料不会改变。")) return;
    setEditing(false);
    setError("");
    setWarnings([]);
    onLockChange(false);
  }

  async function fetchPreview() {
    setBusy(true); onLockChange(true); setError("");
    try {
      const result = await sourceApi.previewContent(source.id, source.content_revision);
      setWarnings(result.warnings);
      openEditor(result.content, result.expected_revision, true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "抓取失败，可手动粘贴正文。");
      onLockChange(false);
    } finally { setBusy(false); }
  }

  async function apply() {
    if (!candidate.trim() || !window.confirm("确认用候选正文替换当前正文？旧草稿文字会保留，但内容变更后需要重新生成。此操作不会自动入库。")) return;
    setBusy(true); setError("");
    try {
      const result = await sourceApi.applyContent(source.id, revision, candidate);
      setEditing(false); setWarnings([]); setCollected(null);
      onApplied(result); onLockChange(false);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "应用失败，候选正文仍保留在这里。"); }
    finally { setBusy(false); }
  }

  async function readCollected() {
    setBusy(true); onLockChange(true); setError("");
    try { setCollected(await sourceApi.getCollectedContent(source.id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "读取订阅内容失败。"); }
    finally { setBusy(false); onLockChange(false); }
  }

  async function restore() {
    if (!window.confirm("恢复为最新订阅内容？这会替换当前补充正文，旧草稿如有变化需重新生成。")) return;
    setBusy(true); onLockChange(true); setError("");
    try { onApplied(await sourceApi.restoreContent(source.id, source.content_revision)); setCollected(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "恢复失败，请刷新后重试。"); }
    finally { setBusy(false); onLockChange(false); }
  }

  return <section className={styles.panel} aria-label="正文完整性" aria-busy={busy}>
    <SourceQuality source={source} />
    {error && <p className={styles.error} role="alert">{error}</p>}
    {!editing && <div className={styles.actions}>
      {source.can_supplement && <>
        <button type="button" disabled={disabled || busy || !source.source_url} onClick={fetchPreview}>{busy ? "处理中…" : "抓取正文预览"}</button>
        <button type="button" disabled={disabled || busy} onClick={() => { setError(""); setWarnings([]); openEditor(source.content, source.content_revision); }}>手动补充正文</button>
      </>}
      {source.content_origin === "supplement" && <button type="button" disabled={disabled || busy} onClick={readCollected}>查看订阅内容</button>}
    </div>}
    {source.can_supplement && !editing && <p className={styles.hint}>只读取原文网页，不调用 AI；预览后由你决定是否应用。动态或受限页面可手动粘贴。</p>}
    {collected && !editing && <details className={styles.collected} open><summary>最新订阅内容 · {collected.title}</summary><SourceContent content={collected.content} className={styles.preview} />{source.can_supplement && <button type="button" disabled={disabled || busy} onClick={restore}>恢复为订阅内容</button>}</details>}
    {editing && <div className={styles.editor}>
      <div className={styles.editorHead}><strong>候选正文 · 尚未应用</strong><span>{candidate.length.toLocaleString("zh-CN")} / 50,000 字符</span></div>
      {warnings.map((warning) => <p className={styles.hint} key={warning}>{warning}</p>)}
      <div className={styles.actions} aria-label="候选正文显示方式">
        <button type="button" disabled={busy} aria-pressed={!preview} onClick={() => setPreview(false)}>编辑正文</button>
        <button type="button" disabled={busy} aria-pressed={preview} onClick={() => setPreview(true)}>预览排版</button>
      </div>
      {preview ? <SourceContent content={candidate || "候选正文为空，请切换编辑。"} ariaLabel="候选正文预览" className={styles.preview} /> : <textarea aria-label="候选正文编辑器" value={candidate} maxLength={50000} rows={12} disabled={busy} onChange={(event) => setCandidate(event.target.value)} />}
      <p className={styles.hint}>支持 Markdown 和 LaTeX。只保留需要学习的正文，并检查公式、导航和评论。</p>
      <div className={styles.actions}>
        <button type="button" className={styles.primary} disabled={busy || !candidate.trim() || candidate.length > 50000} onClick={apply}>{busy ? "正在应用…" : "确认应用正文"}</button>
        <button type="button" disabled={busy} onClick={closeEditor}>取消补充</button>
      </div>
    </div>}
  </section>;
}
