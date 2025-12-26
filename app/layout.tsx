import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "장학금, 채용 대시보드",
  description: "성균관대 장학금, 채용/모집 대시보드",
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

