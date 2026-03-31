import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "高考志愿助手",
  description: "通过多轮对话补全学生档案，在条件成熟后给出可解释、可追溯的高考志愿推荐。"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
