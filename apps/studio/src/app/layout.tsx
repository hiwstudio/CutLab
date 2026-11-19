import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CutLab",
  description: "Timeline-based video editing with an AI director inside",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased dark"
    >
      <body className="min-h-full flex flex-col bg-zinc-950 text-zinc-100">
        {children}
      </body>
    </html>
  );
}
