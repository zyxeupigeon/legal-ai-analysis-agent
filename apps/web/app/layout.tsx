import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "法律AI产品分析",
  description: "法律AI分析Agent单用户本地原型",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
