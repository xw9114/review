"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { Icon } from "@/components/icon";
import { feedApi } from "@/lib/api";
import type {
  CleaningMode,
  FeedSource,
  FeedSourceInput,
  FeedSourceType,
  FeedSyncResult,
} from "@/lib/types";

import styles from "./feed-source-manager.module.css";

const emptyDraft: FeedSourceInput = {
  name: "",
  source_type: "rss",
  endpoint: "",
  cleaning_mode: "auto",
  enabled: true,
};

const cleaningOptions: Array<{
  value: CleaningMode;
  label: string;
  description: string;
}> = [
  { value: "auto", label: "按需清洗", description: "正文太短时才调用 Crawl4AI" },
  { value: "feed", label: "使用订阅正文", description: "最快，也最节省服务器资源" },
  { value: "crawl4ai", label: "始终清洗原文", description: "更完整，但同步时间更长" },
];

const statusLabels = {
  never: "尚未同步",
  success: "同步正常",
  partial: "部分完成",
  failed: "同步失败",
};

function formatTime(value: string | null) {
  if (!value) return "还没有同步记录";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function resultText(result: FeedSyncResult) {
  return `${result.feed_source_name}：新增 ${result.created}，更新 ${result.updated}，未变化 ${result.unchanged}，清洗 ${result.cleaned}。`;
}

export function FeedSourceManager() {
  const [sources, setSources] = useState<FeedSource[]>([]);
  const [draft, setDraft] = useState<FeedSourceInput>(emptyDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState<number | "all" | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    feedApi
      .list()
      .then((items) => {
        if (!cancelled) setSources(items);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "订阅源读取失败。");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function reload() {
    setSources(await feedApi.list());
  }

  function changeType(sourceType: FeedSourceType) {
    setDraft((current) => ({ ...current, source_type: sourceType, endpoint: "" }));
  }

  function editSource(source: FeedSource) {
    setEditingId(source.id);
    setDraft({
      name: source.name,
      source_type: source.source_type,
      endpoint: source.endpoint,
      cleaning_mode: source.cleaning_mode,
      enabled: source.enabled,
    });
    setError("");
    setNotice("");
  }

  function resetEditor() {
    setEditingId(null);
    setDraft(emptyDraft);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      if (editingId) {
        await feedApi.update(editingId, draft);
        setNotice(`“${draft.name.trim()}”已经更新。`);
      } else {
        await feedApi.create(draft);
        setNotice(`“${draft.name.trim()}”已经加入订阅源。`);
      }
      resetEditor();
      await reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "订阅源保存失败。");
    } finally {
      setSaving(false);
    }
  }

  async function toggleSource(source: FeedSource) {
    setError("");
    setNotice("");
    try {
      await feedApi.update(source.id, { enabled: !source.enabled });
      setNotice(source.enabled ? `“${source.name}”已停用。` : `“${source.name}”已启用。`);
      await reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "状态更新失败。");
    }
  }

  async function syncSource(source: FeedSource) {
    setSyncing(source.id);
    setError("");
    setNotice("");
    try {
      const result = await feedApi.sync(source.id);
      setNotice(resultText(result));
      await reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "同步失败。");
      await reload().catch(() => undefined);
    } finally {
      setSyncing(null);
    }
  }

  async function syncAll() {
    setSyncing("all");
    setError("");
    setNotice("");
    try {
      const result = await feedApi.syncAll();
      setNotice(
        `已同步 ${result.succeeded}/${result.sources} 个来源：新增 ${result.created}，清洗 ${result.cleaned}${result.failed_sources ? `，来源失败 ${result.failed_sources}` : ""}。`,
      );
      await reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "批量同步失败。");
    } finally {
      setSyncing(null);
    }
  }

  return (
    <section className={styles.manager}>
      {error && (
        <div className={styles.error} role="alert">
          <div><strong>这一步没有完成</strong><span>{error}</span></div>
          <button type="button" onClick={() => setError("")} aria-label="关闭错误"><Icon name="close" size={15} /></button>
        </div>
      )}
      {notice && (
        <div className={styles.notice} role="status">
          <Icon name="check" size={15} /><span>{notice}</span>
          <button type="button" onClick={() => setNotice("")} aria-label="关闭提示"><Icon name="close" size={14} /></button>
        </div>
      )}

      <div className={styles.board}>
        <form className={styles.editor} onSubmit={save}>
          <div className={styles.editorHead}>
            <span>{editingId ? "EDIT SOURCE" : "NEW SOURCE"}</span>
            <h2>{editingId ? "调整这条信息水路" : "接一条新的信息水路"}</h2>
            <p>这里只保存订阅地址。内容仍要经过你的收件箱，才会成为知识。</p>
          </div>

          <div className={styles.typeSwitch} aria-label="订阅源类型">
            {(["rss", "rsshub"] as FeedSourceType[]).map((type) => (
              <button key={type} type="button" data-active={draft.source_type === type} onClick={() => changeType(type)} disabled={saving}>
                {type === "rss" ? "普通 RSS / Atom" : "RSSHub 路由"}
              </button>
            ))}
          </div>

          <label className={styles.field}>
            <span>显示名称</span>
            <input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} maxLength={120} placeholder="例如：少数派效率专题" required disabled={saving} />
          </label>
          <label className={styles.field}>
            <span>{draft.source_type === "rss" ? "完整 RSS 地址" : "RSSHub 路由"}</span>
            <input value={draft.endpoint} onChange={(event) => setDraft((current) => ({ ...current, endpoint: event.target.value }))} maxLength={2048} placeholder={draft.source_type === "rss" ? "https://example.com/feed.xml" : "/github/issue/DIYgod/RSSHub"} required disabled={saving} />
            <small>{draft.source_type === "rss" ? "只允许公网 http/https 地址。" : "只填写从 / 开始的路由，域名由服务器统一管理。"}</small>
          </label>

          <fieldset className={styles.cleaning}>
            <legend>正文处理</legend>
            {cleaningOptions.map((option) => (
              <label key={option.value} data-active={draft.cleaning_mode === option.value}>
                <input type="radio" name="cleaning-mode" value={option.value} checked={draft.cleaning_mode === option.value} onChange={() => setDraft((current) => ({ ...current, cleaning_mode: option.value }))} disabled={saving} />
                <span><strong>{option.label}</strong><small>{option.description}</small></span>
              </label>
            ))}
          </fieldset>

          <label className={styles.enabled}>
            <input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))} disabled={saving} />
            <span><strong>保存后立即启用</strong><small>停用只暂停同步，不删除已经收进来的资料。</small></span>
          </label>

          <div className={styles.editorActions}>
            <button className={styles.saveButton} type="submit" disabled={saving || !draft.name.trim() || !draft.endpoint.trim()}><Icon name="check" size={15} />{saving ? "正在保存…" : editingId ? "保存调整" : "添加订阅源"}</button>
            {editingId && <button className={styles.cancelButton} type="button" onClick={resetEditor} disabled={saving}>取消编辑</button>}
          </div>
        </form>

        <div className={styles.ledger}>
          <div className={styles.ledgerHead}>
            <div><span>ACTIVE CHANNELS</span><h2>订阅清单</h2><p>{sources.filter((source) => source.enabled).length} 条水路正在开放</p></div>
            <button className={styles.syncAll} type="button" onClick={syncAll} disabled={syncing !== null || !sources.some((source) => source.enabled)}><Icon name="refresh" size={15} />{syncing === "all" ? "同步中…" : "同步全部"}</button>
          </div>

          {loading ? (
            <div className={styles.loading}><i /><i /><i /><span>正在读取订阅源…</span></div>
          ) : sources.length ? (
            <ol className={styles.sourceRows}>
              {sources.map((source, index) => (
                <li key={source.id} data-enabled={source.enabled}>
                  <div className={styles.rowIndex}>{String(index + 1).padStart(2, "0")}</div>
                  <div className={styles.rowMain}>
                    <div className={styles.rowTitle}>
                      <div><strong>{source.name}</strong><span>{source.source_type.toUpperCase()} · {source.cleaning_mode === "auto" ? "按需清洗" : source.cleaning_mode === "feed" ? "订阅正文" : "Crawl4AI"}</span></div>
                      <em data-status={source.last_sync_status}>{statusLabels[source.last_sync_status]}</em>
                    </div>
                    <code>{source.endpoint}</code>
                    <div className={styles.metrics}>
                      <span>{formatTime(source.last_synced_at)}</span>
                      <span>新增 {source.last_created}</span>
                      <span>更新 {source.last_updated}</span>
                      <span>清洗 {source.last_cleaned}</span>
                    </div>
                    {source.last_error && <p className={styles.rowError}>{source.last_error}</p>}
                    <div className={styles.rowActions}>
                      <button type="button" onClick={() => syncSource(source)} disabled={!source.enabled || syncing !== null}><Icon name="refresh" size={13} />{syncing === source.id ? "同步中…" : "立即同步"}</button>
                      <button type="button" onClick={() => editSource(source)} disabled={syncing !== null}><Icon name="edit" size={13} />编辑</button>
                      <button type="button" onClick={() => toggleSource(source)} disabled={syncing !== null}>{source.enabled ? "停用" : "启用"}</button>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <div className={styles.empty}>
              <Icon name="rss" size={32} /><strong>还没有订阅源</strong>
              <p>从一条稳定的 RSS 开始。以后再慢慢补充 RSSHub 路由。</p>
            </div>
          )}

          <div className={styles.ledgerFoot}>
            <span><Icon name="link" size={14} />同步后的文章会进入资料收件箱。</span>
            <Link href="/sources">前往整理<Icon name="arrow-up-right" size={14} /></Link>
          </div>
        </div>
      </div>
    </section>
  );
}
