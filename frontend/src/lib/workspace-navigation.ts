import type { IconName } from "@/components/icon";

export const workspaceNavigation = [
  { label: "工作台", items: [
    { id: "dashboard", href: "/", label: "今日概览", icon: "grid" },
  ] },
  { label: "收集与整理", items: [
    { id: "sources", href: "/sources", label: "资料收件箱", icon: "inbox" },
    { id: "drafts", href: "/drafts", label: "草稿审核", icon: "draft" },
  ] },
  { label: "知识与复习", items: [
    { id: "knowledge", href: "/knowledge", label: "我的知识库", icon: "library" },
    { id: "review", href: "/review", label: "每日复习", icon: "clock" },
  ] },
  { label: "来源管理", items: [
    { id: "feeds", href: "/feeds", label: "订阅源", icon: "rss" },
  ] },
] as const satisfies readonly {
  label: string;
  items: readonly { id: string; href: string; label: string; icon: IconName }[];
}[];

export type WorkspacePage = (typeof workspaceNavigation)[number]["items"][number]["id"];

export function workspaceLabel(page: WorkspacePage) {
  for (const group of workspaceNavigation) {
    const item = group.items.find((entry) => entry.id === page);
    if (item) return item.label;
  }
  return "我的空间";
}
