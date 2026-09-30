import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "知衡 · 个人知识复习系统",
    template: "%s · 知衡",
  },
  description: "把个人笔记转化为持续更新的知识能力模型。",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="zh-CN"
      className="h-full antialiased"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: 'try{document.documentElement.dataset.theme=localStorage.getItem("theme")==="dark"?"dark":"light"}catch{}' }} />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
