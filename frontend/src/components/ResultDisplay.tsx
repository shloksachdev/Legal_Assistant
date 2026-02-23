"use client";

import React from "react";

interface ResultDisplayProps {
  response: string;
  plan?: {
    steps: Array<{
      step_id: number;
      action: string;
      params: Record<string, string>;
    }>;
  };
  isLoading: boolean;
}

export default function ResultDisplay({ response, plan, isLoading }: ResultDisplayProps) {
  if (isLoading) {
    return (
      <div className="glass-card animate-pulse-glow" style={{ padding: "32px", textAlign: "center" }}>
        <div className="spinner" style={{ margin: "0 auto 16px", width: "28px", height: "28px" }} />
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
          Executing deterministic graph traversal...
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "4px" }}>
          Probabilistic discovery → Deterministic retrieval → Synthesis
        </p>
      </div>
    );
  }

  if (!response) return null;

  return (
    <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Execution Plan */}
      {plan && plan.steps && plan.steps.length > 0 && (
        <div className="glass-card" style={{ padding: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="var(--accent-blue)">
              <path d="M1.5 3.25c0-.966.784-1.75 1.75-1.75h2.5c.966 0 1.75.784 1.75 1.75v2.5A1.75 1.75 0 0 1 5.75 7.5h-2.5A1.75 1.75 0 0 1 1.5 5.75Zm1.75-.25a.25.25 0 0 0-.25.25v2.5c0 .138.112.25.25.25h2.5a.25.25 0 0 0 .25-.25v-2.5a.25.25 0 0 0-.25-.25ZM8.5 3.25c0-.966.784-1.75 1.75-1.75h2.5c.966 0 1.75.784 1.75 1.75v2.5a1.75 1.75 0 0 1-1.75 1.75h-2.5A1.75 1.75 0 0 1 8.5 5.75Zm1.75-.25a.25.25 0 0 0-.25.25v2.5c0 .138.112.25.25.25h2.5a.25.25 0 0 0 .25-.25v-2.5a.25.25 0 0 0-.25-.25ZM1.5 10.25c0-.966.784-1.75 1.75-1.75h2.5c.966 0 1.75.784 1.75 1.75v2.5a1.75 1.75 0 0 1-1.75 1.75h-2.5a1.75 1.75 0 0 1-1.75-1.75Zm1.75-.25a.25.25 0 0 0-.25.25v2.5c0 .138.112.25.25.25h2.5a.25.25 0 0 0 .25-.25v-2.5a.25.25 0 0 0-.25-.25Z" />
            </svg>
            <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
              Execution Plan
            </span>
            <span className="badge badge-blue">{plan.steps.length} step{plan.steps.length > 1 ? "s" : ""}</span>
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {plan.steps.map((step, i) => (
              <div key={i} className="animate-slide-in" style={{ animationDelay: `${i * 100}ms`, display: "flex", alignItems: "center", gap: "6px" }}>
                <div style={{
                  width: "22px", height: "22px",
                  borderRadius: "50%",
                  background: "var(--accent-blue-muted)",
                  border: "1px solid rgba(88, 166, 255, 0.3)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "11px", fontWeight: 600, color: "var(--accent-blue)",
                }}>
                  {step.step_id}
                </div>
                <code style={{
                  fontSize: "12px", background: "var(--bg-tertiary)",
                  padding: "2px 6px", borderRadius: "4px", color: "var(--accent-blue)",
                }}>
                  {step.action}
                </code>
                {i < plan.steps.length - 1 && (
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="var(--text-muted)">
                    <path d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06Z" />
                  </svg>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Response */}
      <div className="glass-card" style={{ padding: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="var(--accent-green)">
            <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm9.78-2.22-5.5 5.5a.749.749 0 0 1-1.275-.326.749.749 0 0 1 .215-.734l5.5-5.5a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042Z" />
          </svg>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
            Legal Analysis
          </span>
          <span className="badge badge-green">Verified</span>
        </div>
        <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(response) }} />
      </div>
    </div>
  );
}

/** Simple markdown → HTML renderer (no dependencies). */
function renderMarkdown(text: string): string {
  if (!text) return "";
  let html = text
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold / italic
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Blockquotes
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    // Bullet lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Tables
    .replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').filter(c => c.trim());
      if (cells.every(c => /^[\s-:]+$/.test(c))) return ''; // separator row
      const tag = 'td';
      return '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
    })
    // Paragraphs
    .replace(/\n\n/g, '</p><p>')
    // Line breaks
    .replace(/\n/g, '<br/>');

  // Wrap consecutive <li> in <ul>
  html = html.replace(/(<li>.*?<\/li>(?:<br\/>)?)+/gs, (match) => {
    return '<ul>' + match.replace(/<br\/>/g, '') + '</ul>';
  });

  // Wrap consecutive <tr> in <table>
  html = html.replace(/(<tr>.*?<\/tr>(?:<br\/>)?)+/gs, (match) => {
    return '<table>' + match.replace(/<br\/>/g, '') + '</table>';
  });

  return `<p>${html}</p>`;
}
