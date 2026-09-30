import { AppShell } from "@/components/app-shell";
import { FeedSourceManager } from "@/components/feed-source-manager";

export default function FeedsPage() {
  return (
    <AppShell
      active="feeds"
      eyebrow="CURATED INPUTS"
      title="让好内容自己来到桌面。"
      description="收好 RSS 和 RSSHub 路由，什么时候同步、如何清洗，都由你决定。"
    >
      <FeedSourceManager />
    </AppShell>
  );
}
