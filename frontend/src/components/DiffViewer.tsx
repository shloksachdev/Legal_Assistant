"use client";

import React, { useState } from "react";

interface DiffViewerProps {
  oldText: string;
  newText: string;
  oldLabel?: string;
  newLabel?: string;
  oldDate?: string;
  newDate?: string;
}

interface DiffLine {
  type: "added" | "removed" | "unchanged";
  content: string;
}

function computeDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");

  // Simple LCS-based diff
  const m = oldLines.length, n = newLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack
  let i = m, j = n;
  const actions: DiffLine[] = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      actions.unshift({ type: "unchanged", content: oldLines[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      actions.unshift({ type: "added", content: newLines[j - 1] });
      j--;
    } else {
      actions.unshift({ type: "removed", content: oldLines[i - 1] });
      i--;
    }
  }

  return actions.length > 0 ? actions : [{ type: "unchanged", content: "(No content)" }];
}

const COLORS = {
  added: { bg: "rgba(16,185,129,0.1)", border: "#10b981", text: "#6ee7b7", marker: "+" },
  removed: { bg: "rgba(239,68,68,0.1)", border: "#ef4444", text: "#fca5a5", marker: "−" },
  unchanged: { bg: "transparent", border: "transparent", text: "#94a3b8", marker: " " },
};

export default function DiffViewer({ oldText, newText, oldLabel, newLabel, oldDate, newDate }: DiffViewerProps) {
  const [collapsed, setCollapsed] = useState(false);
  const lines = computeDiff(oldText, newText);

  const addedCount = lines.filter(l => l.type === "added").length;
  const removedCount = lines.filter(l => l.type === "removed").length;

  return (
    <div style={{
      borderRadius: "16px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: "rgba(0,0,0,0.3)",
      overflow: "hidden",
      marginTop: "8px",
      marginBottom: "8px",
    }}>
      {/* Header */}
      <div
        onClick={() => setCollapsed(!collapsed)}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 16px",
          background: "rgba(255,255,255,0.03)",
          borderBottom: collapsed ? "none" : "1px solid rgba(255,255,255,0.06)",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "14px" }}>{collapsed ? "▶" : "▼"}</span>
          <div>
            <div style={{ fontSize: "12px", fontWeight: 600, color: "#f8fafc" }}>
              {oldLabel || "Previous Version"} → {newLabel || "Current Version"}
            </div>
            <div style={{ fontSize: "10px", color: "#64748b", marginTop: "2px" }}>
              {oldDate && newDate ? `${oldDate} → ${newDate}` : "Version comparison"}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          {addedCount > 0 && (
            <span style={{
              padding: "2px 8px", borderRadius: "9999px",
              background: "rgba(16,185,129,0.15)", color: "#10b981",
              fontSize: "10px", fontWeight: 600,
            }}>
              +{addedCount}
            </span>
          )}
          {removedCount > 0 && (
            <span style={{
              padding: "2px 8px", borderRadius: "9999px",
              background: "rgba(239,68,68,0.15)", color: "#ef4444",
              fontSize: "10px", fontWeight: 600,
            }}>
              −{removedCount}
            </span>
          )}
        </div>
      </div>

      {/* Diff body */}
      {!collapsed && (
        <div style={{
          maxHeight: "400px",
          overflowY: "auto",
          padding: "4px 0",
        }}>
          {lines.map((line, idx) => {
            const style = COLORS[line.type];
            return (
              <div key={idx} style={{
                display: "flex",
                background: style.bg,
                borderLeft: `3px solid ${style.border}`,
                padding: "2px 12px 2px 8px",
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                fontSize: "12px",
                lineHeight: "1.7",
                minHeight: "22px",
              }}>
                <span style={{
                  width: "20px",
                  flexShrink: 0,
                  color: style.text,
                  fontWeight: 700,
                  textAlign: "center",
                  opacity: 0.7,
                  userSelect: "none",
                }}>
                  {style.marker}
                </span>
                <span style={{
                  color: style.text,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {line.content || " "}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Parses a unified diff string into old/new text for DiffViewer.
 * Used by ChatInterface to detect and render diff blocks.
 */
export function parseDiffBlock(diffText: string): { oldText: string; newText: string } | null {
  const lines = diffText.split("\n");
  const oldLines: string[] = [];
  const newLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("@@")) continue;
    if (line.startsWith("-")) {
      oldLines.push(line.slice(1));
    } else if (line.startsWith("+")) {
      newLines.push(line.slice(1));
    } else {
      const content = line.startsWith(" ") ? line.slice(1) : line;
      oldLines.push(content);
      newLines.push(content);
    }
  }

  if (oldLines.length === 0 && newLines.length === 0) return null;
  return { oldText: oldLines.join("\n"), newText: newLines.join("\n") };
}
