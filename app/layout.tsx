import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "성균관대 공지",
  description: "성균관대학교 공지 검색 및 분류별 조회",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}

