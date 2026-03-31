import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gaokao Assistant MVP",
  description: "Dialogue-first gaokao planning assistant with dossier, shortlist, compare, and source traceability."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

