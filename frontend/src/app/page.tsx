"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import { useAuth } from "@/components/SessionWrapper";
import ChatInterface from "@/components/ChatInterface";
import ChatInput from "@/components/QueryPanel";
import ScopeSelector from "@/components/ScopeSelector";
import InteractiveGraph from "@/components/InteractiveGraph";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

interface ToolCall {
  tool: string;
  input: Record<string, string> | string;
  output_preview: string;
}

interface TimelineEvent {
  event_index: number;
  event_type: string;
  valid_from: string;
  valid_to?: string;
  action?: {
    action_id: string;
    action_type: string;
    description: string;
    effective_date: string;
    source_ref: string;
  };
  diff?: string | null;
}

interface TimelineData {
  work_id: string;
  work_title: string;
  total_versions: number;
  events: TimelineEvent[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  tool_calls?: ToolCall[];
  suggestions?: string[];
  timeline?: TimelineData | null;
}

interface SchemaStats {
  nodes: { works: number; expressions: number; actions: number; total: number };
  status: string;
}

interface ChatSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export default function Home() {
  const { user, loading: authLoading, signOut } = useAuth();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<SchemaStats | null>(null);
  const [isSeeding, setIsSeeding] = useState(false);
  const [showPanel, setShowPanel] = useState(true);
  const [showChatList, setShowChatList] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chatSummaries, setChatSummaries] = useState<ChatSummary[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage.getItem("templex_chat_summaries");
      if (!raw) return [];
      return JSON.parse(raw) as ChatSummary[];
    } catch {
      return [];
    }
  });
  const [scope, setScope] = useState<{ reference_date: string; domains: string[]; jurisdictions: string[] } | null>(null);
  const [showScopeSelector, setShowScopeSelector] = useState(false);
  const [streamingText, setStreamingText] = useState<string>("");
  const [statusLogs, setStatusLogs] = useState<string[]>([]);

  // Helpers for localStorage-backed chat list
  const STORAGE_KEY_SUMMARIES = "templex_chat_summaries";
  const STORAGE_KEY_PREFIX = "templex_chat_";

  const persistSummaries = (summaries: ChatSummary[]) => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(STORAGE_KEY_SUMMARIES, JSON.stringify(summaries));
    } catch {
      // ignore quota errors
    }
  };

  const persistMessages = (id: string, msgs: Message[]) => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(
        `${STORAGE_KEY_PREFIX}${id}`,
        JSON.stringify(msgs)
      );
    } catch {
      // ignore quota errors
    }
  };

  const loadMessagesForSession = (id: string): Message[] => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage.getItem(`${STORAGE_KEY_PREFIX}${id}`);
      if (!raw) return [];
      return JSON.parse(raw) as Message[];
    } catch {
      return [];
    }
  };

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      window.location.href = "/login";
    }
  }, [authLoading, user]);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/schema`);
      if (res.ok) setStats(await res.json());
    } catch {
      // noop
    }
  };

  // Load server stats when user session is available
  useEffect(() => {
    if (user) {
      void (async () => {
        try {
          const res = await fetch(`${API_BASE}/api/schema`);
          if (res.ok) setStats(await res.json());
        } catch {
          // noop
        }
      })();
    }
  }, [user]);

  const createSession = async (sessionScope?: typeof scope) => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: sessionScope }),
      });
      if (res.ok) {
        const data = await res.json();
        const id = data.session_id as string;
        const now = new Date().toISOString();
        const newSummary: ChatSummary = {
          id,
          title: "New chat",
          createdAt: now,
          updatedAt: now,
        };
        setSessionId(id);
        setMessages([]);
        setScope(sessionScope || null);
        setShowScopeSelector(false);
        setChatSummaries((prev) => {
          const next = [newSummary, ...prev.filter((c) => c.id !== id)];
          persistSummaries(next);
          return next;
        });
        persistMessages(id, []);
      }
    } catch {
      setError("Failed to connect to server. Ensure backend is running.");
    }
  };

  const handleSend = async (message: string) => {
    if (!sessionId) {
      setError("No active session — start the backend server first.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setStreamingText("");

    // Add user message immediately
    const userMsg: Message = { role: "user", content: message };
    setMessages((prev) => {
      const next = [...prev, userMsg];
      if (sessionId) {
        persistMessages(sessionId, next);
        setChatSummaries((prevSummaries) => {
          const now = new Date().toISOString();
          const updated = prevSummaries.map((c) =>
            c.id === sessionId
              ? {
                  ...c,
                  title:
                    c.title === "New chat"
                      ? (message.length > 60 ? message.slice(0, 60) + "…" : message)
                      : c.title,
                  updatedAt: now,
                }
              : c
          );
          persistSummaries(updated);
          return updated;
        });
      }
      return next;
    });

    // Clear backend statuses and start polling
    try {
      await fetch(`${API_BASE}/api/chat/status/clear/${sessionId}`, { method: "POST" });
    } catch { /* noop */ }
    setStatusLogs([]);

    const statusInterval = setInterval(async () => {
      try {
        const statusRes = await fetch(`${API_BASE}/api/chat/status/${sessionId}`);
        if (statusRes.ok) {
          const data = await statusRes.json();
          setStatusLogs(data.logs || []);
        }
      } catch { /* noop */ }
    }, 500);

    try {
      // Try streaming first
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
      });

      if (!res.ok || !res.body) {
        // Fall back to non-streaming
        const fallbackRes = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, message }),
        });
        if (!fallbackRes.ok) {
          const err = await fallbackRes.json().catch(() => ({}));
          throw new Error(err.detail || `Error: ${fallbackRes.status}`);
        }
        const data = await fallbackRes.json();
        const assistantMsg: Message = {
          role: "assistant",
          content: data.response,
          tool_calls: data.tool_calls || [],
          suggestions: data.suggestions || [],
          timeline: data.timeline || null,
        };
        setMessages((prev) => {
          const next = [...prev, assistantMsg];
          if (sessionId) persistMessages(sessionId, next);
          return next;
        });
        setIsLoading(false);
        return;
      }

      // Read SSE stream
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";
      let finalToolCalls: ToolCall[] = [];
      let finalTimeline: TimelineData | null = null;
      let finalSuggestions: string[] = [];
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const chunk = JSON.parse(line.slice(6));

            if (chunk.type === "token") {
              accumulated += chunk.content;
              setStreamingText(accumulated);
            } else if (chunk.type === "tool_call") {
              // Tool-call chunks are surfaced in final "done" payload.
            } else if (chunk.type === "done") {
              accumulated = chunk.content || accumulated;
              finalToolCalls = chunk.tool_calls || [];
              finalTimeline = chunk.timeline || null;
              finalSuggestions = chunk.suggestions || [];
            } else if (chunk.type === "error") {
              throw new Error(chunk.content);
            }
          } catch {
            // Skip malformed SSE lines
          }
        }
      }

      // Finalize: clear streaming state and add to messages
      setStreamingText("");
      const assistantMsg: Message = {
        role: "assistant",
        content: accumulated,
        tool_calls: finalToolCalls,
        suggestions: finalSuggestions,
        timeline: finalTimeline,
      };
      setMessages((prev) => {
        const next = [...prev, assistantMsg];
        if (sessionId) {
          persistMessages(sessionId, next);
          setChatSummaries((prevSummaries) => {
            const now = new Date().toISOString();
            const updated = prevSummaries.map((c) =>
              c.id === sessionId ? { ...c, updatedAt: now } : c
            );
            persistSummaries(updated);
            return updated;
          });
        }
        return next;
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "Request failed";
      setError(errMsg);
      setStreamingText("");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `⚠️ ${errMsg}` },
      ]);
      if (sessionId) {
        const next = [
          ...messages,
          { role: "assistant", content: `⚠️ ${errMsg}` } as Message,
        ];
        persistMessages(sessionId, next);
      }
    } finally {
      clearInterval(statusInterval);
      setIsLoading(false);
    }
  };

  const handleSeed = async () => {
    setIsSeeding(true);
    try {
      const res = await fetch(`${API_BASE}/api/seed`, { method: "POST" });
      if (res.ok) await fetchStats();
    } catch { /* noop */ }
    setIsSeeding(false);
  };

  const handleNewChat = () => {
    if (isLoading) return;
    setShowScopeSelector(true);
  };

  const handleStartSession = (newScope: { reference_date: string; domains: string[]; jurisdictions: string[] }) => {
    createSession(newScope);
  };

  const handleDeleteChat = (id: string) => {
    if (isLoading) return;

    setChatSummaries((prev) => {
      const next = prev.filter((c) => c.id !== id);
      persistSummaries(next);
      return next;
    });

    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(`${STORAGE_KEY_PREFIX}${id}`);
      } catch {
        // ignore
      }
    }

    if (id === sessionId) {
      const remaining = chatSummaries.filter((c) => c.id !== id);
      if (remaining.length > 0) {
        const nextId = remaining[0].id;
        setSessionId(nextId);
        const stored = loadMessagesForSession(nextId);
        setMessages(stored);
      } else {
        setSessionId(null);
        setMessages([]);
      }
    }
  };

  const handleExport = () => {
    if (messages.length === 0) return;
    const chatTitle = chatSummaries.find((c) => c.id === sessionId)?.title || "TempLex Research";
    const now = new Date().toLocaleString();

    let md = `# ${chatTitle}\n\n`;
    md += `> Exported from TempLex GraphRAG on ${now}\n\n---\n\n`;

    for (const msg of messages) {
      if (msg.role === "user") {
        md += `## 🧑 User Query\n\n${msg.content}\n\n`;
      } else {
        md += `## ⚖️ TempLex Analysis\n\n${msg.content}\n\n`;
        if (msg.tool_calls && msg.tool_calls.length > 0) {
          md += `### Methodology (Tool Provenance)\n\n`;
          for (const tc of msg.tool_calls) {
            md += `- **${tc.tool}**: \`${typeof tc.input === "string" ? tc.input : JSON.stringify(tc.input)}\`\n`;
            md += `  - Result: ${tc.output_preview}\n`;
          }
          md += `\n`;
        }
      }
      md += `---\n\n`;
    }

    md += `\n*Generated by TempLex GraphRAG — Deterministic Temporal Legal Reasoning*\n`;

    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${chatTitle.replace(/[^a-zA-Z0-9 ]/g, "").replace(/\s+/g, "_")}_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSelectChat = (id: string) => {
    if (isLoading) return;
    setSessionId(id);
    const stored = loadMessagesForSession(id);
    setMessages(stored);
    setShowScopeSelector(false);
    setShowChatList(true);
  };

  // Show loading while checking auth
  if (authLoading || !user) {
    return (
      <div style={{
        height: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: "var(--bg-primary)",
      }}>
        <div className="spinner" style={{ width: "32px", height: "32px" }} />
      </div>
    );
  }

  const userName = user.user_metadata?.full_name || user.email || "User";
  const userAvatar = user.user_metadata?.avatar_url;
  const userInitials = userName
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-primary)" }}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <header className="glass-card" style={{
        borderTop: "none",
        borderLeft: "none",
        borderRight: "none",
        borderRadius: "0 0 32px 32px",
        margin: "0 16px 16px 16px",
        padding: "12px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            width: "32px", height: "32px", borderRadius: "50%",
            background: "linear-gradient(135deg, var(--accent-blue), #bc8cff)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "14px", fontWeight: 800, color: "white",
          }}>T</div>
          <div>
            <h1 style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.1 }}>
              TempLex GraphRAG
            </h1>
            <p style={{ fontSize: "10px", color: "var(--text-muted)" }}>
              Temporal Legal Reasoning Chat
            </p>
          </div>
        </div>

        {/* Scope badges */}
        {scope && (
          <div style={{ display: "flex", gap: "6px", overflow: "hidden" }}>
            <div className="badge badge-blue" style={{ fontSize: "10px", whiteSpace: "nowrap" }}>
              📅 {scope.reference_date}
            </div>
            {scope.domains.length > 0 && (
              <div className="badge" style={{ fontSize: "10px", whiteSpace: "nowrap", background: "rgba(139,92,246,0.15)", color: "#8b5cf6", border: "1px solid rgba(139,92,246,0.2)" }}>
                ⚖️ {scope.domains.join(" + ")}
              </div>
            )}
            {scope.jurisdictions.length > 0 && (
              <div className="badge badge-green" style={{ fontSize: "10px", whiteSpace: "nowrap" }}>
                🏛️ {scope.jurisdictions.join(" + ")}
              </div>
            )}
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="badge badge-blue" style={{ fontSize: "10px" }}>LangChain</span>
          <span className="badge badge-green" style={{ fontSize: "10px" }}>ReAct</span>

          <button
            onClick={handleNewChat}
            className="btn-secondary"
            style={{ fontSize: "11px", padding: "4px 10px", marginLeft: "8px" }}
            disabled={isLoading}
          >
            + New Chat
          </button>

          {messages.length > 0 && (
            <button
              onClick={handleExport}
              className="btn-secondary"
              style={{ fontSize: "11px", padding: "4px 8px" }}
              disabled={isLoading}
            >
              ⬇ Export
            </button>
          )}

          <button
            onClick={() => setShowPanel(!showPanel)}
            className="btn-secondary"
            style={{ fontSize: "11px", padding: "4px 8px" }}
          >
            {showPanel ? "◀" : "▶"} Graph
          </button>

          {/* User Profile & Sign Out */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginLeft: "8px" }}>
            {userAvatar ? (
              <Image
                src={userAvatar}
                alt={userName}
                width={28}
                height={28}
                style={{
                  width: "28px", height: "28px", borderRadius: "50%",
                  border: "2px solid var(--accent-blue)",
                }}
              />
            ) : (
              <div style={{
                width: "28px", height: "28px", borderRadius: "50%",
                background: "linear-gradient(135deg, var(--accent-blue), #bc8cff)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "11px", fontWeight: 700, color: "white",
              }}>
                {userInitials}
              </div>
            )}
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 500, maxWidth: "100px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {userName}
            </span>
            <button
              onClick={signOut}
              className="btn-secondary"
              style={{
                fontSize: "10px", padding: "4px 10px",
                color: "var(--accent-red, #f85149)",
                borderColor: "rgba(248,81,73,0.3)",
              }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Content ───────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", gap: "20px", padding: "0 20px 20px 20px" }}>
        {/* Chat area */}
        <div className="glass-card" style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          overflow: "hidden",
          borderRadius: "28px",
        }}>
          {/* Messages */}
          <div style={{
            flex: 1,
            overflow: "auto",
            padding: "0 20px 20px 20px",
          }}>
            <div style={{ maxWidth: "760px", width: "100%", margin: "0 auto" }}>
              {(!sessionId || showScopeSelector) ? (
                <ScopeSelector apiBase={API_BASE} onStart={handleStartSession} />
              ) : (
                <ChatInterface
                  messages={messages}
                  isLoading={isLoading}
                  streamingText={streamingText || undefined}
                  statusLogs={statusLogs}
                  onSuggestionClick={handleSend}
                />
              )}
            </div>
          </div>

          {/* Error bar */}
          {error && (
            <div style={{
              padding: "6px 20px",
              background: "rgba(248,81,73,0.1)",
              borderTop: "1px solid rgba(248,81,73,0.2)",
              fontSize: "12px",
              color: "var(--accent-red)",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}>
              <span>⚠️</span> {error}
              <button
                onClick={() => setError(null)}
                style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--accent-red)", cursor: "pointer", fontSize: "14px" }}
              >✕</button>
            </div>
          )}

          {/* Chat input */}
          <div style={{ borderTop: "1px solid var(--border-default)" }}>
            <ChatInput onSend={handleSend} isLoading={isLoading} showSuggestions={messages.length === 0} />
          </div>
        </div>

        {/* Right panel */}
        {showPanel && (
          <div style={{
            width: "340px",
            borderLeft: "1px solid var(--border-default)",
            background: "rgba(255,255,255,0.01)",
            display: "flex",
            flexDirection: "column",
            padding: "16px 16px 20px 16px",
            gap: "16px",
            flexShrink: 0,
            overflowY: "auto",
          }}>
            {/* Saved chats */}
            <div className="glass-card" style={{
              padding: "14px",
              display: "flex",
              flexDirection: "column",
              minHeight: 0,
              width: "100%",
              overflow: "hidden",
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
                <button
                  type="button"
                  onClick={() => setShowChatList((prev) => !prev)}
                  className="btn-secondary"
                  style={{
                    fontSize: "12px",
                    padding: "4px 10px",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  <span>Chats</span>
                  <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{chatSummaries.length}</span>
                  <span style={{ fontSize: "10px", opacity: 0.8 }}>{showChatList ? "▾" : "▸"}</span>
                </button>
                <button
                  onClick={handleNewChat}
                  className="btn-secondary"
                  style={{ fontSize: "10px", padding: "4px 8px" }}
                  disabled={isLoading}
                >
                  + New
                </button>
              </div>
              {showChatList && (
                chatSummaries.length === 0 ? (
                  <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "8px" }}>
                    New chats will appear here.
                  </p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px", overflowY: "auto", paddingRight: "4px", maxHeight: "210px" }}>
                    {chatSummaries.map((chat) => {
                      const isActive = chat.id === sessionId;
                      return (
                        <div
                          key={chat.id}
                          onClick={() => handleSelectChat(chat.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              handleSelectChat(chat.id);
                            }
                          }}
                          role="button"
                          tabIndex={isLoading ? -1 : 0}
                          aria-disabled={isLoading}
                          style={{
                            textAlign: "left",
                            borderRadius: "18px",
                            padding: "8px 14px",
                            border: "1px solid " + (isActive ? "var(--accent-blue)" : "var(--border-default)"),
                            background: isActive ? "var(--accent-blue-muted)" : "transparent",
                            cursor: isLoading ? "not-allowed" : "pointer",
                            fontSize: "12px",
                            color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                            opacity: isLoading ? 0.6 : 1,
                            transition: "all 0.2s ease",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                            <div
                              style={{
                                flex: 1,
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                marginBottom: "2px",
                              }}
                            >
                              {chat.title || "Untitled chat"}
                            </div>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteChat(chat.id);
                              }}
                              style={{
                                border: "none",
                                background: "transparent",
                                color: "var(--text-muted)",
                                cursor: "pointer",
                                fontSize: "12px",
                              }}
                              disabled={isLoading}
                            >
                              ✕
                            </button>
                          </div>
                          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                            {new Date(chat.updatedAt).toLocaleString()}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )
              )}
            </div>

            {/* Interactive Graph */}
            <div className="glass-card" style={{ padding: "14px", width: "100%", overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-primary)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Knowledge Graph
                </span>
                <button
                  onClick={handleSeed}
                  className="btn-secondary"
                  style={{ fontSize: "10px", padding: "4px 8px" }}
                  disabled={isSeeding}
                >
                  {isSeeding ? "Seeding..." : stats && stats.nodes.total > 0 ? "Reseed" : "Load Seed Data"}
                </button>
              </div>

              {/* Stats row */}
              {stats && (
                <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                  {[
                    { label: "Works", count: stats.nodes.works, color: "#3b82f6" },
                    { label: "Expr", count: stats.nodes.expressions, color: "#10b981" },
                    { label: "Actions", count: stats.nodes.actions, color: "#f59e0b" },
                  ].map((s) => (
                    <div key={s.label} style={{
                      flex: 1, textAlign: "center", padding: "8px",
                      borderRadius: "12px", border: "1px solid var(--border-muted)",
                    }}>
                      <div style={{ fontSize: "18px", fontWeight: 800, color: s.color }}>{s.count}</div>
                      <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>{s.label}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* Live interactive graph */}
              <InteractiveGraph apiBase={API_BASE} />
            </div>

            {/* System Details Dropdown */}
            <details className="glass-card" style={{ padding: "14px", flexShrink: 0, width: "100%", overflow: "hidden" }}>
              <summary style={{
                cursor: "pointer",
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
                outline: "none",
                display: "flex",
                alignItems: "center",
                gap: "8px"
              }}>
                System Details
                <span style={{ fontSize: "9px", opacity: 0.7 }}>(Session, Pipeline)</span>
              </summary>

              <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", gap: "20px" }}>
                {/* Session info */}
                <div>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Session
                  </span>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px", fontFamily: "monospace" }}>
                    {sessionId ? sessionId.slice(0, 8) + "..." : "Not connected"}
                  </p>
                  <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                    {messages.length} message{messages.length !== 1 ? "s" : ""}
                  </p>
                </div>

                {/* Architecture info */}
                <div>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Pipeline
                  </span>
                  <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    {[
                      { icon: "🔍", label: "resolve_reference_tool", desc: "Semantic search → Work ID" },
                      { icon: "📅", label: "get_version_tool", desc: "Point-in-time retrieval" },
                      { icon: "🔗", label: "trace_history_tool", desc: "Causal chain + diffs" },
                      { icon: "⚡", label: "aggregate_impact_tool", desc: "Multi-hop aggregation" },
                      { icon: "🇮🇳", label: "fetch_indian_cases_tool", desc: "Live Indian Kanoon data" },
                      { icon: "🌐", label: "fetch_live_cases_tool", desc: "Live CourtListener data" },
                      { icon: "📥", label: "ingest_document_tool", desc: "On-demand ingestion" },
                    ].map((t) => (
                      <div key={t.label} style={{ fontSize: "11px", display: "flex", gap: "8px", alignItems: "flex-start" }}>
                        <span style={{ fontSize: "14px" }}>{t.icon}</span>
                        <div>
                          <div style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{t.label}</div>
                          <div style={{ color: "var(--text-muted)", fontSize: "10px" }}>{t.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </details>
          </div>
        )}
      </div>

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
