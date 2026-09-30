import { AppShell } from "@/components/app-shell";
import { DashboardOverview } from "@/components/dashboard-overview";

export default function Home() {
  return (
    <AppShell
      active="dashboard"
      eyebrow="A LITTLE BETTER, EVERY DAY"
      title="今天，也有新的收获。"
      description="留住灵感，连接知识。让每一次学习都有迹可循。"
    >
      <DashboardOverview />
    </AppShell>
  );
}
