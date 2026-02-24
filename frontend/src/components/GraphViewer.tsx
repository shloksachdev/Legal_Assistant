"use client";

import React from "react";

interface GraphNode {
  work_id?: string;
  title?: string;
  work_type?: string;
  expr_id?: string;
  action_id?: string;
}

interface SchemaStats {
  nodes: {
    works: number;
    expressions: number;
    actions: number;
    total: number;
  };
  status: string;
}

interface GraphViewerProps {
  stats?: SchemaStats | null;
  onSeed?: () => void;
  isSeeding?: boolean;
}

export default function GraphViewer({ stats, onSeed, isSeeding }: GraphViewerProps) {
  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="var(--accent-blue)">
            <path d="M8.5.75a.75.75 0 0 0-1.5 0v1.5H5.75a.75.75 0 0 0 0 1.5H7v1.984a5.512 5.512 0 0 0-3.637 2.19L2.22 6.78a.751.751 0 0 0-1.042.018.751.751 0 0 0-.018 1.042L2.5 9.18a5.526 5.526 0 0 0-.453 1.57H.75a.75.75 0 0 0 0 1.5h1.297c.096.54.27 1.054.51 1.527l-1.117 1.117a.749.749 0 0 0 .326 1.275.749.749 0 0 0 .734-.215l1.143-1.143A5.497 5.497 0 0 0 8 16.5a5.497 5.497 0 0 0 4.357-2.189l1.143 1.143a.749.749 0 0 0 1.275-.326.749.749 0 0 0-.215-.734l-1.117-1.117c.24-.473.414-.987.51-1.527h1.297a.75.75 0 0 0 0-1.5h-1.297a5.526 5.526 0 0 0-.453-1.57l1.34-1.34a.751.751 0 0 0-.018-1.042.751.751 0 0 0-1.042-.018l-1.143 1.144A5.512 5.512 0 0 0 8.5 5.734V3.75h1.25a.75.75 0 0 0 0-1.5H8.5ZM8 7a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z" />
          </svg>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>Knowledge Graph</span>
        </div>

        {onSeed && (
          <button
            onClick={onSeed}
            className="btn-secondary"
            disabled={isSeeding}
            style={{ fontSize: "12px" }}
          >
            {isSeeding ? (
              <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <span className="spinner" style={{ width: "12px", height: "12px" }} />
                Seeding...
              </span>
            ) : stats && stats.nodes.total > 0 ? (
              "Reseed Data"
            ) : (
              "Load Seed Data"
            )}
          </button>
        )}
      </div>

      {stats ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: "12px",
          }}
        >
          <StatCard
            label="Works"
            count={stats.nodes.works}
            color="var(--accent-blue)"
            icon="📜"
            description="Abstract legal concepts"
          />
          <StatCard
            label="Expressions"
            count={stats.nodes.expressions}
            color="var(--accent-green)"
            icon="📝"
            description="Temporal text versions"
          />
          <StatCard
            label="Actions"
            count={stats.nodes.actions}
            color="var(--accent-orange)"
            icon="⚡"
            description="Legislative events"
          />
        </div>
      ) : (
        <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)", fontSize: "13px" }}>
          <p>No graph data loaded.</p>
          <p style={{ marginTop: "4px" }}>Click &quot;Load Seed Data&quot; to populate the graph.</p>
        </div>
      )}

      {stats && (
        <div style={{ marginTop: "16px", display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={{
            width: "6px", height: "6px", borderRadius: "50%",
            background: stats.status === "connected" ? "var(--accent-green)" : "var(--accent-red)",
          }} />
          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            KuzuDB {stats.status} • {stats.nodes.total} total nodes
          </span>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  count,
  color,
  icon,
  description,
}: {
  label: string;
  count: number;
  color: string;
  icon: string;
  description: string;
}) {
  return (
    <div
      style={{
        background: "var(--bg-canvas)",
        border: "1px solid var(--border-muted)",
        borderRadius: "6px",
        padding: "12px",
        textAlign: "center",
        transition: "border-color 0.2s",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = color)}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-muted)")}
    >
      <div style={{ fontSize: "20px", marginBottom: "4px" }}>{icon}</div>
      <div style={{ fontSize: "24px", fontWeight: 700, color }}>{count}</div>
      <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-primary)" }}>{label}</div>
      <div style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "2px" }}>{description}</div>
    </div>
  );
}
