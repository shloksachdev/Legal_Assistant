"use client";

import React, { useState } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

const SUGGESTIONS = [
  "What is the punishment for sedition in India as of August 2024?",
  "Trace the evolution of Article 6 of the Brazilian Constitution",
  "What was the impact of BNS replacing the IPC?",
  "How has the rape law in India evolved?",
];

export default function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSend(message.trim());
      setMessage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div style={{
      borderTop: "1px solid var(--border-default)",
      background: "var(--bg-secondary)",
      padding: "16px 20px",
    }}>
      {/* Suggestions (only show when no messages have been sent yet) */}
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            onClick={() => { setMessage(s); }}
            className="btn-secondary"
            style={{ fontSize: "11px", padding: "3px 8px" }}
          >
            {s.length > 50 ? s.slice(0, 50) + "…" : s}
          </button>
        ))}
      </div>

      {/* Input bar */}
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: "10px", alignItems: "flex-end" }}>
        <div style={{ flex: 1, position: "relative" }}>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about laws at specific points in time..."
            rows={1}
            style={{
              width: "100%",
              background: "var(--bg-canvas)",
              border: "1px solid var(--border-default)",
              borderRadius: "12px",
              padding: "10px 14px",
              color: "var(--text-primary)",
              fontSize: "14px",
              resize: "none",
              outline: "none",
              fontFamily: "inherit",
              lineHeight: "1.5",
              maxHeight: "120px",
              minHeight: "42px",
              overflow: "auto",
              transition: "border-color 0.15s",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--accent-blue)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 120) + "px";
            }}
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !message.trim()}
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "12px",
            background: message.trim() ? "var(--accent-blue)" : "var(--bg-tertiary)",
            border: "none",
            cursor: message.trim() ? "pointer" : "default",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "background 0.15s, transform 0.1s",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => message.trim() && (e.currentTarget.style.background = "var(--accent-blue-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = message.trim() ? "var(--accent-blue)" : "var(--bg-tertiary)")}
        >
          {isLoading ? (
            <span className="spinner" style={{ width: "16px", height: "16px", borderColor: "var(--border-default)", borderTopColor: "white" }} />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={message.trim() ? "var(--bg-primary)" : "var(--text-muted)"} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </form>
    </div>
  );
}
