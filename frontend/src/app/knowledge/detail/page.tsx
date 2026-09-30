import { AppShell } from "@/components/app-shell";
import { KnowledgeDetail } from "@/components/knowledge-detail";

export default function Page() {
  return <AppShell active="knowledge" eyebrow="KNOWLEDGE / READ & REMEMBER" title="把知识读懂，再记牢。" description="摘要、要点和题目，都保留在同一个地方。"><KnowledgeDetail /></AppShell>;
}
