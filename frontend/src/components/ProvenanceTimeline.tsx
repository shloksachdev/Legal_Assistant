"use client";

import React from "react";

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
  old_text?: string | null;
  new_text?: string;
  diff?: string | null;
}

interface ProvenanceTimelineProps {
  events?: TimelineEvent[];
  workTitle?: string;
  workId?: string;
  totalVersions?: number;
}

export default function ProvenanceTimeline({
  events,
  workTitle,
  workId,
  totalVersions,
}: ProvenanceTimelineProps) {
  if (!events || events.length === 0) return null;

  return (
    <div className="glass-card animate-fade-in" style={{ padding: "24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "20px" }}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="var(--accent-purple)">
          <path d="M1.643 3.143.427 1.927A.25.25 0 0 1 .604 1.5h2.792a.25.25 0 0 1 .177.427L2.357 3.143a.25.25 0 0 1-.354 0ZM8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1Zm-5.5 7a5.5 5.5 0 1 1 11 0 5.5 5.5 0 0 1-11 0ZM8 4.5a.75.75 0 0 1 .75.75v2.5h1.75a.75.75 0 0 1 0 1.5H8a.75.75 0 0 1-.75-.75v-3.25A.75.75 0 0 1 8 4.5Z" />
        </svg>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
          Provenance Timeline
        </span>
        {totalVersions && (
          <span className="badge badge-blue">{totalVersions} version{totalVersions > 1 ? "s" : ""}</span>
        )}
      </div>

      {workTitle && (
        <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "16px" }}>
          <code style={{ color: "var(--accent-blue)", background: "var(--bg-tertiary)", padding: "2px 6px", borderRadius: "4px", fontSize: "12px" }}>
            {workId}
          </code>{" "}
          {workTitle}
        </p>
      )}

      {/* Timeline */}
      <div style={{ position: "relative", paddingLeft: "24px" }}>
        {/* Vertical line */}
        <div
          style={{
            position: "absolute",
            left: "7px",
            top: "4px",
            bottom: "4px",
            width: "2px",
            background: "var(--border-default)",
          }}
        />

        {events.map((event, i) => (
          <div
            key={i}
            className="animate-slide-in"
            style={{
              animationDelay: `${i * 150}ms`,
              position: "relative",
              marginBottom: i < events.length - 1 ? "20px" : "0",
            }}
          >
            {/* Timeline dot */}
            <div
              style={{
                position: "absolute",
                left: "-20px",
                top: "4px",
                width: "12px",
                height: "12px",
                borderRadius: "50%",
                background: getEventColor(event.event_type),
                border: "2px solid var(--bg-secondary)",
              }}
            />

            {/* Event card */}
            <div
              style={{
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-muted)",
                borderRadius: "6px",
                padding: "12px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: "6px",
                  flexWrap: "wrap",
                }}
              >
                <span className={`badge badge-${getEventBadgeColor(event.event_type)}`}>
                  {event.event_type}
                </span>
                <span style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "monospace" }}>
                  {event.valid_from}
                  {event.valid_to ? ` → ${event.valid_to}` : " → present"}
                </span>
              </div>

              {event.action && (
                <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "6px" }}>
                  {event.action.description}
                </p>
              )}

              {event.action?.source_ref && (
                <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  Source: <em>{event.action.source_ref}</em>
                </p>
              )}

              {/* Diff preview */}
              {event.diff && (
                <details style={{ marginTop: "8px" }}>
                  <summary
                    style={{
                      fontSize: "12px",
                      color: "var(--accent-blue)",
                      cursor: "pointer",
                      userSelect: "none",
                    }}
                  >
                    View textual diff
                  </summary>
                  <pre
                    style={{
                      marginTop: "6px",
                      fontSize: "11px",
                      background: "var(--bg-canvas)",
                      border: "1px solid var(--border-default)",
                      borderRadius: "4px",
                      padding: "8px",
                      overflow: "auto",
                      maxHeight: "200px",
                      color: "var(--text-secondary)",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {event.diff}
                  </pre>
                </details>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getEventColor(type: string): string {
  switch (type) {
    case "enactment":
      return "var(--accent-green)";
    case "amendment":
      return "var(--accent-orange)";
    case "repeal":
    case "replacement":
      return "var(--accent-red)";
    default:
      return "var(--accent-blue)";
  }
}

function getEventBadgeColor(type: string): string {
  switch (type) {
    case "enactment":
      return "green";
    case "amendment":
      return "orange";
    case "repeal":
    case "replacement":
      return "red";
    default:
      return "blue";
  }
}
