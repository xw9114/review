"use client";

import Link from "next/link";
import { Icon } from "@/components/icon";
import { SourceContent } from "@/components/source-content";
import { SourceSupplement } from "@/components/source-supplement";
import { SourceActions } from "@/components/sources/source-actions";
import { SourceQueue } from "@/components/sources/source-queue";
import { SourceRelevance } from "@/components/sources/source-relevance";
import { useSourceWorkspace } from "@/components/sources/use-source-workspace";
import { sourceDate, sourceStatusOptions } from "@/lib/source-workspace";
import styles from "./source-inbox.module.css";

export function SourceInbox() {
  const workspace = useSourceWorkspace();
  const { selected, busy, loading, loadFailed, operation } = workspace;
  return <section className={styles.inbox}>
    <div className={styles.overview}>
      <div className={styles.overviewCopy}><span className={styles.liveDot} /><div><strong>资料收集与整理</strong><small>日序和订阅资料，统一处理</small></div></div>
      <div className={styles.overviewActions}>
        <Link className={styles.feedLink} href="/feeds">管理订阅<Icon name="arrow-up-right" size={12} /></Link>
        <button className={styles.analyzeButton} type="button" onClick={workspace.analyzePending} disabled={busy || loadFailed}><Icon name="chart" size={15} />{operation === "score-batch" ? "正在分析…" : "分析待整理"}</button>
        <button className={styles.syncButton} type="button" onClick={workspace.syncNotebook} disabled={busy || loadFailed}><Icon name="refresh" size={15} />{operation === "sync" ? "正在同步…" : "同步日序"}</button>
      </div>
    </div>

    {workspace.error && <div className={styles.error} role="alert"><div><strong>这一步没有完成</strong><span>{workspace.error}</span></div><button type="button" onClick={() => workspace.setError("")} aria-label="关闭错误"><Icon name="close" size={15} /></button></div>}
    {workspace.notice && <div className={styles.notice} role="status"><Icon name="check" size={15} /><span>{workspace.notice}</span><button type="button" onClick={() => workspace.setNotice("")} aria-label="关闭提示"><Icon name="close" size={14} /></button></div>}

    <div className={styles.statusBar} aria-label="资料状态筛选">
      {sourceStatusOptions.map((option) => <button key={option.value} type="button" disabled={busy} aria-pressed={workspace.status === option.value}
        className={workspace.status === option.value ? styles.statusActive : ""} onClick={() => workspace.changeStatus(option.value)}><span>{option.label}</span><small>{option.note}</small></button>)}
    </div>
    <div className={styles.workspace}>
      <SourceQueue documents={workspace.documents} visible={workspace.visibleDocuments} drafts={workspace.drafts} selectedId={selected?.id ?? null}
        status={workspace.status} filters={workspace.filters} loading={loading} loadFailed={loadFailed} busy={busy}
        onFilter={workspace.changeFilters} onSelect={workspace.selectDocument} onRetry={workspace.retryLoad} />
      <div className={styles.detail} id="source-detail" aria-busy={loading}>
        {loading || loadFailed ? <div className={styles.detailEmpty}><span>YOUR READING DESK</span><Icon name={loadFailed ? "refresh" : "book"} size={32} /><strong>{loadFailed ? "等资料加载后，再继续整理" : "正在准备阅读区…"}</strong><p>{loadFailed ? "请在列表中重试读取，避免操作尚未确认的旧资料。" : "正文、草稿状态和主题会一起载入。"}</p></div> : selected ? <>
          <div className={styles.detailHead}><div><span>SOURCE / {selected.external_id}</span><h2>{selected.title}</h2><p>{sourceDate(selected.source_created_at)} 收录于 {selected.source_name}{selected.author ? ` · ${selected.author}` : ""}</p>{selected.source_url && <a className={styles.sourceLink} href={selected.source_url} target="_blank" rel="noreferrer">查看原文<Icon name="arrow-up-right" size={13} /></a>}</div><span className={styles.statusBadge} data-status={selected.status}>{sourceStatusOptions.find((option) => option.value === selected.status)?.label}</span></div>
          <SourceSupplement key={selected.id} source={selected} disabled={workspace.working || workspace.manualDirty} onLockChange={workspace.setContentLocked} onApplied={workspace.applySupplement} />
          <SourceContent className={styles.sourceText} content={selected.content || "这条资料没有补充内容。"} />
          <SourceRelevance source={selected} categories={workspace.categories} topics={workspace.topics} busy={busy}
            analyzing={operation === "score-one"} onAnalyze={workspace.analyzeSelected} />
          <SourceActions source={selected} categories={workspace.categories} topics={workspace.topics} editor={workspace.editor}
            existingDraft={workspace.existingDraft} busy={busy} generating={operation === "generate"} accepting={operation === "accept"}
            dirty={workspace.manualDirty} onEdit={workspace.patchEditor} onCategory={workspace.changeCategory}
            onGenerate={workspace.generateDraft} onAccept={workspace.accept} onIgnore={workspace.ignoreSelected} />
        </> : <div className={styles.detailEmpty}><span>YOUR READING DESK</span><Icon name="leaf" size={32} /><strong>{workspace.filters.query || workspace.filters.provider ? "调整筛选，找到想读的资料" : "从列表选一条资料"}</strong><p>读一遍，再决定它要不要成为你的知识。</p></div>}
      </div>
    </div>
    <div className={styles.footnote}><span><Icon name="leaf" size={14} />只有你点击分析时，资料才会发送到已配置的 Embedding 服务。</span><span>YOU DECIDE WHAT BECOMES KNOWLEDGE.</span></div>
  </section>;
}
