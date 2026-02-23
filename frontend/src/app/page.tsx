"use client";

import React, { useState, useEffect, useCallback } from "react";
import ChatInterface from "@/components/ChatInterface";
import ChatInput from "@/components/QueryPanel";
import GraphViewer from "@/components/GraphViewer";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<SchemaStats | null>(null);
  const [isSeeding, setIsSeeding] = useState(false);
  const [showPanel, setShowPanel] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chatSummaries, setChatSummaries] = useState<ChatSummary[]>([]);

  // Helpers for localStorage‑backed chat list
  const STORAGE_KEY_SUMMARIES = "templex_chat_summaries";
  const STORAGE_KEY_PREFIX = "templex_chat_";

  const loadStoredChats = () => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY_SUMMARIES);
      if (!raw) return;
      const parsed = JSON.parse(raw) as ChatSummary[];
      setChatSummaries(parsed);
    } catch {
      // ignore corrupt storage
    }
  };

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

  // Create session on mount and load any stored chats
  useEffect(() => {
    loadStoredChats();
    createSession();
    fetchStats();
  }, []);

  const createSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/new`, { method: "POST" });
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
        setChatSummaries((prev) => {
          const next = [newSummary, ...prev.filter((c) => c.id !== id)];
          persistSummaries(next);
          return next;
        });
        persistMessages(id, []);
      }
    } catch {
      // Server might not be running
    }
  };

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/schema`);
      if (res.ok) setStats(await res.json());
    } catch { /* noop */ }
  }, []);

  const handleSend = async (message: string) => {
    if (!sessionId) {
      setError("No active session — start the backend server first.");
      return;
    }

    setIsLoading(true);
    setError(null);

    // Add user message immediately
    const userMsg: Message = { role: "user", content: message };
    setMessages((prev) => {
      const next = [...prev, userMsg];
      if (sessionId) {
        persistMessages(sessionId, next);
        // Set title from first user message if it's still the placeholder
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

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error: ${res.status}`);
      }

      const data = await res.json();
      const assistantMsg: Message = {
        role: "assistant",
        content: data.response,
        tool_calls: data.tool_calls,
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
    createSession();
  };

  const handleSelectChat = (id: string) => {
    setSessionId(id);
    const stored = loadMessagesForSession(id);
    setMessages(stored);
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-primary)" }}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <header style={{
        borderBottom: "1px solid var(--border-default)",
        background: "var(--bg-secondary)",
        padding: "10px 20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            width: "28px", height: "28px", borderRadius: "8px",
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

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="badge badge-blue" style={{ fontSize: "10px" }}>LangChain</span>
          <span className="badge badge-green" style={{ fontSize: "10px" }}>ReAct</span>

          <button onClick={handleNewChat} className="btn-secondary" style={{ fontSize: "11px", padding: "4px 10px", marginLeft: "8px" }}>
            + New Chat
          </button>

          <button
            onClick={() => setShowPanel(!showPanel)}
            className="btn-secondary"
            style={{ fontSize: "11px", padding: "4px 8px" }}
          >
            {showPanel ? "◀" : "▶"} Graph
          </button>
        </div>
      </header>

      {/* ── Main Content ───────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Chat area */}
        <div style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}>
          {/* Messages */}
          <div style={{
            flex: 1,
            overflow: "auto",
            padding: "0 20px",
          }}>
            <div style={{ maxWidth: "800px", margin: "0 auto" }}>
              <ChatInterface messages={messages} isLoading={isLoading} />
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
          <ChatInput onSend={handleSend} isLoading={isLoading} />
        </div>

        {/* Right panel */}
        {showPanel && (
          <div style={{
            width: "300px",
            borderLeft: "1px solid var(--border-default)",
            background: "var(--bg-canvas)",
            overflow: "auto",
            padding: "16px",
            flexShrink: 0,
          }}>
            <GraphViewer stats={stats} onSeed={handleSeed} isSeeding={isSeeding} />

            {/* Saved chats */}
            <div style={{ marginTop: "16px", padding: "12px", background: "var(--bg-secondary)", borderRadius: "6px", border: "1px solid var(--border-muted)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Chats
                </span>
                <button
                  onClick={handleNewChat}
                  className="btn-secondary"
                  style={{ fontSize: "10px", padding: "2px 8px" }}
                >
                  + New
                </button>
              </div>
              {chatSummaries.length === 0 ? (
                <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  New chats will appear here.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "180px", overflowY: "auto" }}>
                  {chatSummaries.map((chat) => {
                    const isActive = chat.id === sessionId;
                    return (
                      <button
                        key={chat.id}
                        onClick={() => handleSelectChat(chat.id)}
                        style={{
                          textAlign: "left",
                          borderRadius: "6px",
                          padding: "6px 8px",
                          border: "1px solid " + (isActive ? "var(--accent-blue)" : "var(--border-muted)"),
                          background: isActive ? "var(--accent-blue-muted)" : "var(--bg-canvas)",
                          cursor: "pointer",
                          fontSize: "11px",
                          color: "var(--text-secondary)",
                        }}
                      >
                        <div
                          style={{
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            marginBottom: "2px",
                          }}
                        >
                          {chat.title || "Untitled chat"}
                        </div>
                        <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                          {new Date(chat.updatedAt).toLocaleString()}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Session info */}
            <div style={{ marginTop: "16px", padding: "12px", background: "var(--bg-secondary)", borderRadius: "6px", border: "1px solid var(--border-muted)" }}>
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
            <div style={{ marginTop: "16px", padding: "12px", background: "var(--bg-secondary)", borderRadius: "6px", border: "1px solid var(--border-muted)" }}>
              <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                Pipeline
              </span>
              <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "6px" }}>
                {[
                  { icon: "🔍", label: "resolve_legal_reference", desc: "Semantic search → Work ID" },
                  { icon: "📅", label: "get_version_at_date", desc: "Point-in-time retrieval" },
                  { icon: "🔗", label: "trace_legislative_history", desc: "Causal chain + diffs" },
                  { icon: "⚡", label: "aggregate_legislative_impact", desc: "Multi-hop aggregation" },
                ].map((t) => (
                  <div key={t.label} style={{ fontSize: "11px", display: "flex", gap: "6px", alignItems: "flex-start" }}>
                    <span>{t.icon}</span>
                    <div>
                      <div style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{t.label}</div>
                      <div style={{ color: "var(--text-muted)", fontSize: "10px" }}>{t.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
