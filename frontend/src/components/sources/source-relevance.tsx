import { sourceScore } from "@/lib/source-workspace";
import type { Category, SourceDocument, Topic } from "@/lib/types";
import styles from "../source-inbox.module.css";

type Props = { source: SourceDocument; categories: Category[]; topics: Topic[]; busy: boolean; analyzing: boolean; onAnalyze: () => void };

export function SourceRelevance({ source, categories, topics, busy, analyzing, onAnalyze }: Props) {
  const topic = topics.find((item) => item.id === source.suggested_topic_id);
  const category = categories.find((item) => item.id === topic?.category_id);

  if (source.processing_status === "scored") return <section className={styles.relevancePanel} data-passed={source.relevance_passed} aria-label="相关性分析结果">
    <div className={styles.relevanceScore}><span>相关度</span><strong>{sourceScore(source.relevance_score)}</strong><em>{source.relevance_method === "embedding" ? "Embedding" : "本地关键词"}</em></div>
    <div className={styles.relevanceCopy}><span>{source.relevance_passed ? "建议保留" : "建议人工复核"}</span><strong>{category && topic ? `${category.name} / ${topic.name}` : "暂无推荐主题"}</strong><p>{source.relevance_reason || "已经完成相关性分析。"}</p></div>
    <button type="button" onClick={onAnalyze} disabled={busy}>重新分析</button>
  </section>;

  if (source.processing_status === "failed") return <div className={styles.analysisState} data-state="failed">
    <div><strong>上次分析没有完成</strong><p>{source.relevance_reason || "Embedding 服务暂时不可用。"}</p></div><button type="button" onClick={onAnalyze} disabled={busy}>重试</button>
  </div>;

  if (source.status !== "pending") return null;
  return <div className={styles.analysisState}><div><strong>相关性分析 · 可选</strong><p>辅助推荐主题；也可以直接选择主题，继续整理。</p></div><button type="button" onClick={onAnalyze} disabled={busy}>{analyzing ? "分析中…" : "分析这条"}</button></div>;
}
