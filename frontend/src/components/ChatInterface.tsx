"use client";

import React, { useRef, useEffect } from "react";
import DiffViewer, { parseDiffBlock } from "./DiffViewer";
import ProvenanceTimeline from "./ProvenanceTimeline";

interface ToolCall {
  tool: string;
  input: Record<string, string> | string;
  output_preview: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  tool_calls?: ToolCall[];
  suggestions?: string[];
  timeline?: any;
}

interface ChatInterfaceProps {
  messages: Message[];
  isLoading: boolean;
  statusLogs?: string[];
  streamingText?: string;
  onSuggestionClick?: (suggestion: string) => void;
}

const TOOL_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  resolve_legal_reference: { label: "Resolve", icon: "🔍", color: "var(--accent-blue)" },
  resolve_reference_tool: { label: "Resolve", icon: "🔍", color: "var(--accent-blue)" },
  get_version_at_date: { label: "Temporal", icon: "📅", color: "var(--accent-green)" },
  get_version_tool: { label: "Temporal", icon: "📅", color: "var(--accent-green)" },
  trace_legislative_history: { label: "Trace", icon: "🔗", color: "var(--accent-purple)" },
  trace_history_tool: { label: "Trace", icon: "🔗", color: "var(--accent-purple)" },
  aggregate_legislative_impact: { label: "Impact", icon: "⚡", color: "var(--accent-orange)" },
  aggregate_impact_tool: { label: "Impact", icon: "⚡", color: "var(--accent-orange)" },
  fetch_live_cases_tool: { label: "Live US", icon: "🌐", color: "#3b82f6" },
  fetch_indian_cases_tool: { label: "Live India", icon: "🇮🇳", color: "#f59e0b" },
  ingest_document_tool: { label: "Ingest", icon: "📥", color: "#8b5cf6" },
};

export default function ChatInterface({ messages, isLoading, statusLogs = [], streamingText, onSuggestionClick }: ChatInterfaceProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, streamingText, statusLogs]);

  if (messages.length === 0 && !isLoading && !streamingText) {
    return <EmptyState />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "20px 0 12px 0", width: "100%" }}>
      {messages.map((msg, i) => (
        <MessageBubble key={i} msg={msg} index={i} isLoading={isLoading} onSuggestionClick={onSuggestionClick} />
      ))}

      {/* ── PIPELINE ACTIVE panel ── */}
      {isLoading && (
        <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "6px" }}>
          <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent-blue)", textTransform: "uppercase", letterSpacing: "0.5px", padding: "0 4px" }}>
            TempLex
          </span>
          <div style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-default)",
            borderRadius: "16px 16px 16px 4px",
            padding: "0",
            minWidth: "420px",
            maxWidth: "560px",
            overflow: "hidden",
            boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
          }}>
            {/* Header bar */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 16px 8px 16px",
              borderBottom: "1px solid var(--border-muted)",
            }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
                <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "0.8px", textTransform: "uppercase" }}>
                  {statusLogs.length > 0 ? "Pipeline Active" : "Connecting..."}
                </span>
                {/* Animated underline */}
                <div style={{ height: "2px", width: "100%", background: "var(--border-muted)", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{
                    height: "100%", width: "40%",
                    background: "linear-gradient(90deg, transparent, var(--accent-blue), transparent)",
                    borderRadius: "2px",
                    animation: "pipeline-scan 1.4s ease-in-out infinite",
                  }} />
                </div>
              </div>
              {statusLogs.length > 0 && (
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 500, marginLeft: "12px", whiteSpace: "nowrap" }}>
                  {statusLogs.length} step{statusLogs.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>

            {/* Log lines */}
            <div style={{
              padding: "10px 14px 12px 14px",
              display: "flex", flexDirection: "column", gap: "3px",
              maxHeight: "260px", overflowY: "auto",
            }}>
              {statusLogs.length === 0 ? (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "4px 0" }}>
                  <span className="spinner" style={{ width: "12px", height: "12px", flexShrink: 0 }} />
                  <span style={{ fontSize: "12px", fontFamily: "monospace", color: "var(--text-muted)" }}>
                    Connecting to reasoning engine...
                  </span>
                </div>
              ) : (
                statusLogs.map((log, idx) => {
                  const isLast = idx === statusLogs.length - 1;
                  return (
                    <div key={idx} style={{
                      display: "flex", alignItems: "flex-start", gap: "8px",
                      padding: "2px 0",
                      opacity: isLast ? 1 : idx >= statusLogs.length - 6 ? 0.75 : 0.45,
                      transition: "opacity 0.3s ease",
                    }}>
                      {/* Icon */}
                      <span style={{ flexShrink: 0, marginTop: "1px", width: "14px", textAlign: "center" }}>
                        {isLast ? (
                          <span className="spinner" style={{ width: "10px", height: "10px", display: "inline-block" }} />
                        ) : (
                          <span style={{ fontSize: "10px", color: "var(--accent-green)" }}>✓</span>
                        )}
                      </span>
                      {/* Text */}
                      <span style={{
                        fontSize: "12px",
                        fontFamily: "monospace",
                        color: isLast ? "var(--text-primary)" : "var(--text-secondary)",
                        lineHeight: "1.4",
                        wordBreak: "break-all",
                      }}>
                        {log}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />

      <style>{`
        @keyframes pipeline-scan {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(350%); }
        }
      `}</style>
    </div>
  );
}

function MessageBubble({ msg, index, isLoading, onSuggestionClick }: { msg: Message; index: number; isLoading: boolean; onSuggestionClick?: (s: string) => void }) {
  const isUser = msg.role === "user";

  return (
    <div
      className="animate-fade-in"
      style={{
        animationDelay: `${Math.min(index * 50, 300)}ms`,
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        gap: "6px",
        width: "100%",
      }}
    >
      {/* Role label */}
      <span style={{
        fontSize: "11px", fontWeight: 600,
        color: isUser ? "var(--text-muted)" : "var(--accent-blue)",
        textTransform: "uppercase", letterSpacing: "0.5px",
        padding: "0 4px",
      }}>
        {isUser ? "You" : "TempLex"}
      </span>

      {/* Message bubble */}
      <div style={{
        maxWidth: isUser ? "72%" : "86%",
        width: "fit-content",
        background: isUser ? "var(--accent-blue)" : "var(--bg-secondary)",
        border: `1px solid ${isUser ? "rgba(88,166,255,0.2)" : "var(--border-default)"}`,
        borderRadius: isUser ? "32px 32px 8px 32px" : "32px 32px 32px 8px",
        padding: "12px 18px",
        boxShadow: "0 10px 24px rgba(0,0,0,0.18)",
      }}>
        {!isUser ? (
          <MarkdownWithDiff content={msg.content} />
        ) : (
          <p style={{ fontSize: "14px", color: "var(--text-primary)", lineHeight: "1.5" }}>{msg.content}</p>
        )}
      </div>

      {/* Tool calls */}
      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", padding: "0 4px", maxWidth: "100%" }}>
          {msg.tool_calls.map((tc, j) => {
            const info = TOOL_LABELS[tc.tool] || { label: tc.tool, icon: "🔧", color: "var(--text-muted)" };
            return (
              <span
                key={j}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "4px",
                  padding: "3px 10px",
                  background: `${info.color}15`,
                  color: info.color,
                  border: `1px solid ${info.color}30`,
                  borderRadius: "9999px",
                  fontWeight: 500,
                  fontSize: "11px",
                }}
              >
                <span>{info.icon}</span>
                {info.label}
              </span>
            );
          })}
        </div>
      )}

      {/* Provenance Timeline */}
      {msg.timeline && msg.timeline.events && msg.timeline.events.length > 0 && (
        <div style={{ maxWidth: "90%", marginTop: "4px" }}>
          <ProvenanceTimeline
            events={msg.timeline.events}
            workTitle={msg.timeline.work_title}
            workId={msg.timeline.work_id}
            totalVersions={msg.timeline.total_versions}
          />
        </div>
      )}

      {/* Follow-up Suggestions */}
      {!isUser && msg.suggestions && msg.suggestions.length > 0 && !isLoading && (
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", padding: "0 4px", maxWidth: "90%" }}>
          {msg.suggestions.map((s, j) => (
            <button
              key={j}
              onClick={() => onSuggestionClick?.(s)}
              style={{
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-default)",
                borderRadius: "9999px",
                padding: "6px 14px",
                fontSize: "12px",
                color: "var(--text-secondary)",
                cursor: "pointer",
                transition: "all 0.2s ease",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                maxWidth: "280px",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--accent-blue)";
                e.currentTarget.style.color = "var(--accent-blue)";
                e.currentTarget.style.background = "var(--accent-blue-muted)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border-default)";
                e.currentTarget.style.color = "var(--text-secondary)";
                e.currentTarget.style.background = "var(--bg-tertiary)";
              }}
            >
              ✨ {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Renders markdown content, replacing ```diff blocks with DiffViewer */
function MarkdownWithDiff({ content }: { content: string }) {
  // Split content by diff code blocks
  const diffRegex = /```diff\n([\s\S]*?)```/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = diffRegex.exec(content)) !== null) {
    // Text before the diff block
    if (match.index > lastIndex) {
      const textBefore = content.slice(lastIndex, match.index);
      parts.push(
        <div key={`text-${lastIndex}`} className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(textBefore) }} />
      );
    }

    // The diff block itself
    const diffContent = match[1];
    const parsed = parseDiffBlock(diffContent);
    if (parsed) {
      parts.push(
        <DiffViewer
          key={`diff-${match.index}`}
          oldText={parsed.oldText}
          newText={parsed.newText}
          oldLabel="Previous Version"
          newLabel="Current Version"
        />
      );
    } else {
      // Fallback to code block
      parts.push(
        <div key={`code-${match.index}`} className="markdown-body" dangerouslySetInnerHTML={{
          __html: `<pre><code>${diffContent}</code></pre>`
        }} />
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Remaining text after last diff block
  if (lastIndex < content.length) {
    parts.push(
      <div key={`text-${lastIndex}`} className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(content.slice(lastIndex)) }} />
    );
  }

  // If no diff blocks found, render normally
  if (parts.length === 0) {
    return <div className="markdown-body" dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} />;
  }

  return <>{parts}</>;
}

function EmptyState() {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "420px",
      gap: "16px",
      textAlign: "center",
      padding: "40px 20px",
    }}>
      <div style={{
        width: "56px",
        height: "56px",
        margin: "12px 0",
        borderRadius: "50%",
        overflow: "hidden",
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
            padding: "8px 16px",
            borderRadius: "9999px",
            fontSize: "11px",
            background: "var(--bg-secondary)",
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
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: var(--accent-blue); text-decoration: underline;">$1</a>')
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
