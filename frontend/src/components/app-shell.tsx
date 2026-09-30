import Link from "next/link";
import type { ReactNode } from "react";
import { workspaceLabel, workspaceNavigation, type WorkspacePage } from "@/lib/workspace-navigation";

import { Icon } from "./icon";
import { ThemeToggle } from "./theme-toggle";

type AppShellProps = {
  active: WorkspacePage;
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function AppShell({ active, eyebrow, title, description, children }: AppShellProps) {
  const breadcrumb = workspaceLabel(active);

  return (
    <div className="app-frame">
      <a href="#main-content" className="skip-link">跳到主要内容</a>
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="知衡首页">
          <span className="brand-mark"><Icon name="layers" size={24} /></span>
          <span><strong>知衡<span className="brand-dot">.</span></strong><small>KNOWLEDGE STUDIO</small></span>
        </Link>
        <div className="workspace-label"><span className="workspace-dot" />我的学习空间</div>
        <nav className="nav-list" aria-label="主导航">
          {workspaceNavigation.map((group) => <div className="nav-group" key={group.label}>
            <p className="nav-caption">{group.label}</p>
            {group.items.map((item) => <Link key={item.id} href={item.href} aria-label={item.label} title={item.label}
              className={active === item.id ? "nav-item active" : "nav-item"} aria-current={active === item.id ? "page" : undefined}>
              <Icon name={item.icon} size={19} /><span>{item.label}</span><span className="nav-active-dot" />
            </Link>)}
          </div>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Icon name="leaf" size={25} />
            <p>每天一点，<br />离融会贯通更近一点。</p>
            <span>STAY CURIOUS.</span>
          </div>
          <div className="profile"><span className="avatar">知</span><div><strong>终身学习者</strong><small>我的个人工作台</small></div><span className="profile-dot" /></div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <div className="breadcrumb"><span>我的空间</span><Icon name="chevron-right" size={13} /><strong>{breadcrumb}</strong></div>
          <div className="topbar-actions">
            <Link href="/knowledge#knowledge-search" className="search-shortcut" aria-label="搜索知识库"><Icon name="search" size={17} /><span>搜索知识库</span></Link>
            <span className="topbar-separator" /><ThemeToggle />
          </div>
        </header>
        <main id="main-content" className="main-area">
          <div className="page-heading">
            <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>
            {active === "dashboard" && <Link href="/knowledge?new=category#new-category" className="button button-dark heading-action"><Icon name="plus" size={17} />新建领域</Link>}
          </div>
          {children}
          <footer className="workspace-footer"><span>慢慢来，知识会生长。</span><span>MADE FOR YOUR CURIOUS MIND <Icon name="leaf" size={13} /></span></footer>
        </main>
      </div>
    </div>
  );
}
