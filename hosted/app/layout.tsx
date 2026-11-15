import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LocalRSI · 智能工作空间",
  description: "受邀成员的 AI 工作空间",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
