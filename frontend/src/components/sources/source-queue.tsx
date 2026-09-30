import Link from "next/link";
import { useEffect, useRef } from "react";
import { Icon } from "@/components/icon";
import { sourceExcerpt } from "@/components/source-content";
import { emptySourceFilters, sourceDate, sourceScore, sourceStatusOptions, type SourceFilters } from "@/lib/source-workspace";
import type { KnowledgeDraft, SourceDocument, SourceStatus } from "@/lib/types";
import styles from "../source-inbox.module.css";

type Props = {
  documents: SourceDocument[];
  visible: SourceDocument[];
  drafts: KnowledgeDraft[];
  selectedId: number | null;
  status: SourceStatus;
  filters: SourceFilters;
  loading: boolean;
  loadFailed: boolean;
  busy: boolean;
  onFilter: (filters: SourceFilters) => void;
  onSelect: (document: SourceDocument) => void;
  onRetry: () => void;
};

export function SourceQueue({ documents, visible, drafts, selectedId, status, filters, loading, loadFailed, busy, onFilter, onSelect, onRetry }: Props) {
  const providers = Array.from(new Map(documents.map((document) => [document.provider, document.source_name])).entries());
  const draftBySource = new Map(drafts.filter((draft) => draft.status !== "approved").map((draft) => [draft.source_document_id, draft]));
  const filtered = Boolean(filters.query || filters.provider);
  const listRef = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const list = listRef.current;
    const button = list?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]');
    if (!list || !button) return;
    const bounds = list.getBoundingClientRect();
    const item = button.getBoundingClientRect();
    if (item.bottom > bounds.bottom) list.scrollTop += item.bottom - bounds.bottom;
    else if (item.top < bounds.top) list.scrollTop -= bounds.top - item.top;
  }, [selectedId, loading, visible]);

  return <section className={styles.sourceList} aria-label="资料列表" aria-busy={loading}>
    <div className={styles.listHeading}>
      <span>{sourceStatusOptions.find((option) => option.value === status)?.label}</span>
      <strong aria-label="资料数量">{loading || loadFailed ? "—" : filtered ? `${visible.length} / ${documents.length}` : String(documents.length).padStart(2, "0")}</strong>
    </div>
    <div className={styles.queueToolbar}>
      <label className={styles.queueSearch}>
        <Icon name="search" size={15} />
        <input type="search" aria-label="搜索资料" placeholder="标题、来源或作者" value={filters.query}
          disabled={busy || loadFailed} onChange={(event) => onFilter({ ...filters, query: event.target.value })} />
      </label>
      <div className={styles.queueFilterRow}>
        <label><span>来源</span><select aria-label="筛选来源" value={filters.provider} disabled={busy || loadFailed}
          onChange={(event) => onFilter({ ...filters, provider: event.target.value })}>
          <option value="">全部来源</option>
          {providers.map(([id, label]) => <option value={id} key={id}>{label}</option>)}
        </select></label>
        {filtered && <button type="button" disabled={busy || loadFailed} onClick={() => onFilter(emptySourceFilters)}>清除筛选</button>}
      </div>
    </div>
    {loading ? <div className={styles.loading}><i /><i /><i /><span>正在读取资料…</span></div> : loadFailed ? (
      <div className={styles.empty}><Icon name="refresh" size={27} /><strong>资料暂时未能加载</strong><p>当前列表尚未确认，请重试后再继续整理。</p><button type="button" className={styles.analyzeButton} onClick={onRetry}>重试读取</button></div>
    ) : visible.length ? (
      <ol ref={listRef}>
        {visible.map((document, index) => {
          const draft = draftBySource.get(document.id);
          return <li key={document.id}><button type="button" className={selectedId === document.id ? styles.sourceActive : ""}
            disabled={busy} aria-pressed={selectedId === document.id} aria-controls="source-detail" onClick={() => onSelect(document)}>
            <span className={styles.sourceNumber}>{String(index + 1).padStart(2, "0")}</span>
            <span className={styles.sourceCopy}>
              <strong>{document.title}</strong><small>{sourceExcerpt(document.content) || "这条资料没有补充内容。"}</small>
              {draft && <span className={styles.draftMarker}><Icon name="draft" size={11} />{draft.status === "stale" ? "草稿需复核" : draft.status === "rejected" ? "草稿已退回" : "草稿待审核"}</span>}
              {document.processing_status === "scored" && <span className={styles.sourceScore} data-passed={document.relevance_passed}>{sourceScore(document.relevance_score)} · {document.relevance_passed ? "相关" : "待复核"}</span>}
              <em>{sourceDate(document.source_created_at)} · {document.source_name}</em>
            </span><Icon name="chevron-right" size={15} />
          </button></li>;
        })}
      </ol>
    ) : <div className={styles.empty}>
      <span className={styles.emptyMark}><Icon name={filtered ? "search" : "inbox"} size={30} /></span>
      <strong>{filtered ? "没有匹配的资料" : status === "pending" ? "没有等待整理的资料" : "这里暂时是空的"}</strong>
      <p>{filtered ? "试试其他关键词或来源，筛选不会改变资料状态。" : status === "pending" ? "同步日序或订阅源，新的资料会来到这里。" : "切换状态，看看其他资料。"}</p>
      {!filtered && status === "pending" && <Link href="/feeds">管理订阅源<Icon name="arrow-up-right" size={13} /></Link>}
    </div>}
  </section>;
}
