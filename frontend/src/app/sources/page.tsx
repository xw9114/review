import { AppShell } from "@/components/app-shell";
import { SourceInbox } from "@/components/source-inbox";

export default function SourcesPage() {
  return (
    <AppShell
      active="sources"
      eyebrow="FROM NOTES TO KNOWLEDGE"
      title="先收进来，再慢慢整理。"
      description="日序与订阅内容会停在这里，由你决定什么值得留下。"
    >
      <SourceInbox />
    </AppShell>
  );
}
