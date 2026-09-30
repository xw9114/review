import { AppShell } from "@/components/app-shell";
import { DraftReview } from "@/components/draft-review";

export default function DraftsPage() {
  return (
    <AppShell
      active="drafts"
      eyebrow="HUMAN IN THE LOOP"
      title="AI 先打草稿，你来定稿。"
      description="修改摘要、要点和题目，只有批准后才会进入知识库。"
    >
      <DraftReview />
    </AppShell>
  );
}
