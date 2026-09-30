import { AppShell } from "@/components/app-shell";
import { ReviewWorkspace } from "@/components/review-workspace";

export default function Page() {
  return <AppShell active="review" eyebrow="DAILY REVIEW" title="让学过的，记得更久。" description="先回忆，再对照，用每一次复习巩固自己的理解。"><ReviewWorkspace /></AppShell>;
}
