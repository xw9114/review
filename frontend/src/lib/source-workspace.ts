import type { Category, SourceDocument, SourceStatus, Topic } from "./types";

export const sourceStatusOptions: { value: SourceStatus; label: string; note: string }[] = [
  { value: "pending", label: "待整理", note: "等待归入知识库" },
  { value: "accepted", label: "已整理", note: "已经生成知识点" },
  { value: "ignored", label: "已忽略", note: "暂时不需要处理" },
  { value: "stale", label: "已失效", note: "来源中已经不存在" },
];

export type SourceFilters = { query: string; provider: string };
export const emptySourceFilters: SourceFilters = { query: "", provider: "" };

export function filterSources(documents: SourceDocument[], filters: SourceFilters) {
  const query = filters.query.trim().toLocaleLowerCase("zh-CN");
  return documents.filter((document) => (!filters.provider || document.provider === filters.provider) &&
    (!query || [document.title, document.source_name, document.author ?? ""].some((text) =>
      text.toLocaleLowerCase("zh-CN").includes(query))));
}

export function preferredSourceTopic(document: SourceDocument | null, categories: Category[], topics: Topic[]) {
  const suggested = topics.find((topic) => topic.id === document?.suggested_topic_id);
  const category = categories.find((item) => item.id === suggested?.category_id) ?? categories[0];
  const topic = suggested ?? topics.find((item) => item.category_id === category?.id);
  return { categoryId: category?.id ?? "", topicId: topic?.id ?? "" } as const;
}

export function sourceDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

export function sourceScore(value: number | null) {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

// Replace, rather than push, so a long triage session does not fill browser history.
export function rememberSource(status: SourceStatus, id: number | null) {
  const url = new URL(window.location.href);
  url.searchParams.set("status", status);
  if (id !== null) url.searchParams.set("source", String(id));
  else url.searchParams.delete("source");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}
