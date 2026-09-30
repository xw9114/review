import { AppShell } from "@/components/app-shell";
import { KnowledgeManager } from "@/components/knowledge-manager";

export default function KnowledgePage() {
  return (
    <AppShell
      active="knowledge"
      eyebrow="YOUR PERSONAL KNOWLEDGE LIBRARY"
      title="给知识，一个自己的位置。"
      description="从一个领域开始，慢慢长出属于你的知识地图。"
    >
      <KnowledgeManager />
    </AppShell>
  );
}
