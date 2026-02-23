import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TempLex GraphRAG — Temporal Legal Reasoning",
  description:
    "Deterministic, CPU-optimized temporal legal reasoning agent powered by SAT-Graph RAG and LRMoo ontology",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ fontFamily: "'Inter', sans-serif" }}>{children}</body>
    </html>
  );
}
