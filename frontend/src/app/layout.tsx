import type { Metadata } from "next";
import "./globals.css";
import { APP_NAME, APP_VERSION } from "@/config/version";

export const metadata: Metadata = {
  title: `${APP_NAME} Profit Approval System`,
  description: "포워딩 영업 손익 관리 및 AI 결재 플랫폼",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
