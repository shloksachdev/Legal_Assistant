"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";

interface GraphNodeData {
  id: string;
  type: "work" | "expression" | "action";
  label: string;
  metadata: Record<string, string>;
}

interface GraphEdgeData {
  source: string;
  target: string;
  relationship: string;
}

interface SimNode extends GraphNodeData {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  pinned: boolean;
}

interface InteractiveGraphProps {
  apiBase: string;
}

const NODE_COLORS: Record<string, string> = {
  work: "#3b82f6",
  expression: "#10b981",
  action: "#f59e0b",
};

const EDGE_COLORS: Record<string, string> = {
  HAS_VERSION: "#3b82f650",
  HAS_PART: "#3b82f640",
  INITIATES: "#10b98150",
  TERMINATES: "#ef444450",
  CAUSED_BY: "#f59e0b40",
};

export default function InteractiveGraph({ apiBase }: InteractiveGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const edgesRef = useRef<GraphEdgeData[]>([]);
  const animRef = useRef<number>(0);
  const dragRef = useRef<{ node: SimNode | null; offsetX: number; offsetY: number }>({ node: null, offsetX: 0, offsetY: 0 });
  const panRef = useRef({ x: 0, y: 0, startX: 0, startY: 0, panning: false });
  const zoomRef = useRef(1);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: SimNode } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nodeCount, setNodeCount] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // Fetch graph data
  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`${apiBase}/api/graph/data`);
        if (!res.ok) throw new Error("Failed to fetch graph data");
        const data = await res.json();

        const cx = 300, cy = 200;
        const nodes: SimNode[] = (data.nodes || []).map((n: GraphNodeData, i: number) => {
          const angle = (2 * Math.PI * i) / (data.nodes.length || 1);
          const r = 80 + Math.random() * 120;
          return {
            ...n,
            x: cx + Math.cos(angle) * r,
            y: cy + Math.sin(angle) * r,
            vx: 0, vy: 0,
            radius: n.type === "work" ? 18 : n.type === "action" ? 14 : 10,
            pinned: false,
          };
        });

        nodesRef.current = nodes;
        edgesRef.current = data.edges || [];
        setNodeCount(nodes.length);
        setLoading(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load graph");
        setLoading(false);
      }
    }
    fetchData();
  }, [apiBase]);

  // Force simulation
  const simulate = useCallback(() => {
    const nodes = nodesRef.current.map((node) => ({ ...node }));
    const edges = edgesRef.current;
    if (nodes.length === 0) return;

    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    // Repulsion (charge)
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = 800 / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (!a.pinned) { a.vx -= fx; a.vy -= fy; }
        if (!b.pinned) { b.vx += fx; b.vy += fy; }
      }
    }

    // Attraction (spring) along edges
    for (const edge of edges) {
      const a = nodeMap.get(edge.source);
      const b = nodeMap.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - 100) * 0.01;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      if (!a.pinned) { a.vx += fx; a.vy += fy; }
      if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
    }

    // Center gravity
    const cx = 300, cy = 200;
    for (const n of nodes) {
      if (n.pinned) continue;
      n.vx += (cx - n.x) * 0.001;
      n.vy += (cy - n.y) * 0.001;
      // Damping
      n.vx *= 0.85;
      n.vy *= 0.85;
      n.x += n.vx;
      n.y += n.vy;
    }
    nodesRef.current = nodes;
  }, []);

  // Draw
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = typeof window !== "undefined" ? (window.devicePixelRatio || 1) : 1;
    const h = canvas.height / dpr;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.translate(panRef.current.x, panRef.current.y);
    ctx.scale(zoomRef.current, zoomRef.current);

    const nodes = nodesRef.current;
    const edges = edgesRef.current;
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    // Draw edges
    for (const edge of edges) {
      const a = nodeMap.get(edge.source);
      const b = nodeMap.get(edge.target);
      if (!a || !b) continue;

      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = EDGE_COLORS[edge.relationship] || "rgba(255,255,255,0.1)";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Arrow
      const angle = Math.atan2(b.y - a.y, b.x - a.x);
      const arrowLen = 8;
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      ctx.beginPath();
      ctx.moveTo(mx + arrowLen * Math.cos(angle - 0.4), my + arrowLen * Math.sin(angle - 0.4));
      ctx.lineTo(mx, my);
      ctx.lineTo(mx + arrowLen * Math.cos(angle + 0.4), my + arrowLen * Math.sin(angle + 0.4));
      ctx.strokeStyle = EDGE_COLORS[edge.relationship] || "rgba(255,255,255,0.15)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    // Draw nodes
    for (const node of nodes) {
      const color = NODE_COLORS[node.type] || "#94a3b8";

      // Glow
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius + 4, 0, Math.PI * 2);
      const glow = ctx.createRadialGradient(node.x, node.y, node.radius, node.x, node.y, node.radius + 8);
      glow.addColorStop(0, color + "40");
      glow.addColorStop(1, "transparent");
      ctx.fillStyle = glow;
      ctx.fill();

      // Circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = color + "30";
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = "#f8fafc";
      ctx.font = `${Math.max(8, 10)}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const shortLabel = node.label.length > 12 ? node.label.slice(0, 12) + "…" : node.label;
      ctx.fillText(shortLabel, node.x, node.y + node.radius + 14);
    }

    ctx.restore();
  }, []);

  // Animation loop
  useEffect(() => {
    if (loading) return;
    let running = true;

    const loop = () => {
      if (!running) return;
      simulate();
      draw();
      animRef.current = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
    };
  }, [loading, simulate, draw]);

  // Resize
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resize = () => {
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    return () => observer.disconnect();
  }, []);

  // Mouse handlers
  const getMousePos = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left - panRef.current.x) / zoomRef.current,
      y: (e.clientY - rect.top - panRef.current.y) / zoomRef.current,
    };
  };

  const findNode = (mx: number, my: number) => {
    for (const n of nodesRef.current) {
      const dx = n.x - mx, dy = n.y - my;
      if (dx * dx + dy * dy < (n.radius + 4) * (n.radius + 4)) return n;
    }
    return null;
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    const { x, y } = getMousePos(e);
    const node = findNode(x, y);
    if (node) {
      dragRef.current = { node, offsetX: x - node.x, offsetY: y - node.y };
      node.pinned = true;
      setIsDragging(true);
    } else {
      panRef.current.panning = true;
      panRef.current.startX = e.clientX - panRef.current.x;
      panRef.current.startY = e.clientY - panRef.current.y;
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (dragRef.current.node) {
      const { x, y } = getMousePos(e);
      dragRef.current.node.x = x - dragRef.current.offsetX;
      dragRef.current.node.y = y - dragRef.current.offsetY;
      dragRef.current.node.vx = 0;
      dragRef.current.node.vy = 0;
    } else if (panRef.current.panning) {
      panRef.current.x = e.clientX - panRef.current.startX;
      panRef.current.y = e.clientY - panRef.current.startY;
    } else {
      // Tooltip
      const { x, y } = getMousePos(e);
      const node = findNode(x, y);
      if (node) {
        const canvas = canvasRef.current;
        if (canvas) {
          const rect = canvas.getBoundingClientRect();
          setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top - 10, node });
        }
      } else {
        setTooltip(null);
      }
    }
  };

  const handleMouseUp = () => {
    if (dragRef.current.node) {
      dragRef.current.node.pinned = false;
      dragRef.current.node = null;
      setIsDragging(false);
    }
    panRef.current.panning = false;
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      zoomRef.current = Math.max(0.3, Math.min(3, zoomRef.current * delta));
    };

    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      canvas.removeEventListener("wheel", handleWheel);
    };
  }, []);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "250px" }}>
        <div className="spinner" style={{ width: "24px", height: "24px" }} />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "12px" }}>
        {error}. Seed the database first.
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%", height: "300px", borderRadius: "16px", overflow: "hidden" }}>
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { handleMouseUp(); setTooltip(null); }}
        style={{ cursor: isDragging ? "grabbing" : "grab", display: "block", width: "100%", height: "100%" }}
      />
      {/* Node count badge */}
      <div style={{
        position: "absolute", top: "8px", right: "8px",
        padding: "4px 10px", borderRadius: "9999px",
        background: "rgba(0,0,0,0.6)", fontSize: "10px", color: "#94a3b8",
      }}>
        {nodeCount} nodes
      </div>
      {/* Tooltip */}
      {tooltip && (
        <div style={{
          position: "absolute",
          left: tooltip.x + 12,
          top: tooltip.y - 40,
          background: "rgba(0,0,0,0.9)",
          border: "1px solid rgba(255,255,255,0.15)",
          borderRadius: "12px",
          padding: "10px 14px",
          pointerEvents: "none",
          zIndex: 10,
          maxWidth: "220px",
        }}>
          <div style={{ fontSize: "12px", fontWeight: 700, color: NODE_COLORS[tooltip.node.type] || "#fff", marginBottom: "4px" }}>
            {tooltip.node.label}
          </div>
          <div style={{ fontSize: "10px", color: "#94a3b8" }}>
            Type: {tooltip.node.type} • ID: {tooltip.node.id}
          </div>
          {Object.entries(tooltip.node.metadata || {}).map(([k, v]) => (
            v && <div key={k} style={{ fontSize: "10px", color: "#64748b" }}>{k}: {v}</div>
          ))}
        </div>
      )}

      <div style={{
        position: "absolute",
        left: "12px",
        bottom: "10px",
        display: "flex",
        alignItems: "center",
        gap: "14px",
        padding: "6px 10px",
        borderRadius: "9999px",
        background: "rgba(0,0,0,0.55)",
        border: "1px solid rgba(255,255,255,0.08)",
        fontSize: "11px",
        color: "#94a3b8",
        pointerEvents: "none",
      }}>
        {[
          { color: NODE_COLORS.work, label: "Work" },
          { color: NODE_COLORS.expression, label: "Expression" },
          { color: NODE_COLORS.action, label: "Action" },
        ].map((item) => (
          <span key={item.label} style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: item.color, display: "inline-block" }} />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
