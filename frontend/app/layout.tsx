import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RR Command Center",
  description: "The Reddington System — Intelligence & Command Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
