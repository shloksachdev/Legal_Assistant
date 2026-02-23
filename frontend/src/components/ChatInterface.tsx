"use client";

import React, { useRef, useEffect } from "react";

interface ToolCall {
  tool: string;
  input: Record<string, string> | string;
  output_preview: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  tool_calls?: ToolCall[];
}

interface ChatInterfaceProps {
  messages: Message[];
  isLoading: boolean;
}

const TOOL_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  resolve_legal_reference: { label: "Resolve", icon: "🔍", color: "var(--accent-blue)" },
  get_version_at_date: { label: "Temporal", icon: "📅", color: "var(--accent-green)" },
  trace_legislative_history: { label: "Trace", icon: "🔗", color: "var(--accent-purple)" },
  aggregate_legislative_impact: { label: "Impact", icon: "⚡", color: "var(--accent-orange)" },
};

export default function ChatInterface({ messages, isLoading }: ChatInterfaceProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return <EmptyState />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px 0" }}>
      {messages.map((msg, i) => (
        <div
          key={i}
          className="animate-fade-in"
          style={{
            animationDelay: `${Math.min(i * 50, 300)}ms`,
            display: "flex",
            flexDirection: "column",
            alignItems: msg.role === "user" ? "flex-end" : "flex-start",
            gap: "6px",
          }}
        >
          {/* Role label */}
          <span style={{
            fontSize: "11px",
            fontWeight: 600,
            color: msg.role === "user" ? "var(--text-muted)" : "var(--accent-blue)",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
            padding: "0 4px",
          }}>
            {msg.role === "user" ? "You" : "TempLex"}
          </span>

          {/* Message bubble */}
          <div style={{
            maxWidth: msg.role === "user" ? "70%" : "90%",
            background: msg.role === "user" ? "var(--accent-blue-muted)" : "var(--bg-secondary)",
            border: `1px solid ${msg.role === "user" ? "rgba(88,166,255,0.2)" : "var(--border-default)"}`,
            borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
            padding: "12px 16px",
          }}>
            {msg.role === "assistant" ? (
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
            ) : (
              <p style={{ fontSize: "14px", color: "var(--text-primary)", lineHeight: "1.5" }}>{msg.content}</p>
            )}
          </div>

          {/* Tool calls */}
          {msg.tool_calls && msg.tool_calls.length > 0 && (
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", padding: "0 4px" }}>
              {msg.tool_calls.map((tc, j) => {
                const info = TOOL_LABELS[tc.tool] || { label: tc.tool, icon: "🔧", color: "var(--text-muted)" };
                return (
                  <span
                    key={j}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      padding: "2px 8px",
                      borderRadius: "10px",
                      fontSize: "11px",
                      fontWeight: 500,
                      background: `${info.color}15`,
                      color: info.color,
                      border: `1px solid ${info.color}30`,
                    }}
                  >
                    <span>{info.icon}</span>
                    {info.label}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      ))}

      {/* Typing indicator */}
      {isLoading && (
        <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "6px" }}>
          <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent-blue)", textTransform: "uppercase", letterSpacing: "0.5px", padding: "0 4px" }}>
            TempLex
          </span>
          <div style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-default)",
            borderRadius: "16px 16px 16px 4px",
            padding: "14px 20px",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}>
            <span className="spinner" style={{ width: "14px", height: "14px" }} />
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>Reasoning with graph traversal...</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "400px",
      gap: "16px",
      textAlign: "center",
      padding: "40px 20px",
    }}>
      <div style={{
        width: "56px",
        height: "56px",
        borderRadius: "16px",
        background: "linear-gradient(135deg, var(--accent-blue), #bc8cff)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "28px",
        fontWeight: 800,
        color: "white",
      }}>
        T
      </div>
      <div>
        <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "4px" }}>
          TempLex GraphRAG
        </h2>
        <p style={{ fontSize: "13px", color: "var(--text-muted)", maxWidth: "400px" }}>
          Ask me about laws at specific points in time. I use deterministic graph traversal to provide provenance-backed legal analysis.
        </p>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center", marginTop: "8px" }}>
        {["🔍 Resolve", "📅 Temporal", "🔗 Trace", "⚡ Impact"].map((tool) => (
          <span key={tool} style={{
            padding: "4px 10px",
            borderRadius: "10px",
            fontSize: "11px",
            background: "var(--bg-tertiary)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-muted)",
          }}>
            {tool}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Simple markdown → HTML renderer */
function renderMarkdown(text: string): string {
  if (!text) return "";
  let html = text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').filter(c => c.trim());
      if (cells.every(c => /^[\s-:]+$/.test(c))) return '';
      return '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
    })
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');

  html = html.replace(/(<li>.*?<\/li>(<br\/>)?)+/gs, (m) =>
    '<ul>' + m.replace(/<br\/>/g, '') + '</ul>'
  );
  html = html.replace(/(<tr>.*?<\/tr>(<br\/>)?)+/gs, (m) =>
    '<table>' + m.replace(/<br\/>/g, '') + '</table>'
  );
  return `<p>${html}</p>`;
}
