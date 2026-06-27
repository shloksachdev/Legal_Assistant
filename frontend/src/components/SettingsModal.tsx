"use client";

import React, { useState, useEffect } from "react";

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  enforced?: boolean; // If true, they can't close without entering a key
}

export function SettingsModal({ open, onOpenChange, enforced = false }: SettingsModalProps) {
  const [hfToken, setHfToken] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("hfToken");
      if (stored) {
        setHfToken(stored);
      }
    }
  }, [open]);

  if (!open) return null;

  const handleSave = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem("hfToken", hfToken);
    }
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onOpenChange(false);
    }, 1000);
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (enforced && !newOpen && typeof window !== "undefined" && !localStorage.getItem("hfToken")) {
      return;
    }
    onOpenChange(newOpen);
  };

  return (
    <div style={{
      position: "fixed",
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: "rgba(0, 0, 0, 0.7)",
      backdropFilter: "blur(4px)",
      zIndex: 9999,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "20px"
    }}>
      <div className="glass-card" style={{
        width: "100%",
        maxWidth: "480px",
        padding: "24px",
        borderRadius: "16px",
        background: "var(--bg-secondary)",
        border: "1px solid var(--border-default)",
        boxShadow: "0 20px 40px rgba(0,0,0,0.4)"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
          <div style={{
            width: "32px", height: "32px", borderRadius: "8px",
            background: "rgba(139, 92, 246, 0.2)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <span style={{ fontSize: "16px" }}>🔑</span>
          </div>
          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 600, color: "var(--text-primary)" }}>
            Bring Your Own Key
          </h2>
        </div>

        <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "20px", lineHeight: "1.5" }}>
          {enforced 
            ? "You've reached the free trial limit of 3 prompts! Please enter your HuggingFace API key to continue chatting. This key is stored securely in your browser and is only sent to our servers."
            : "Enter your HuggingFace API key to bypass the free trial limit. This key is stored securely in your browser."}
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
              HuggingFace API Key (HF_TOKEN)
            </label>
            <input
              type="password"
              placeholder="hf_..."
              value={hfToken}
              onChange={(e) => setHfToken(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-canvas)",
                border: "1px solid var(--border-default)",
                borderRadius: "8px",
                padding: "10px 14px",
                color: "var(--text-primary)",
                fontSize: "14px",
                outline: "none",
                fontFamily: "inherit",
              }}
              onFocus={(e) => (e.target.style.borderColor = "var(--accent-blue)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
            />
          </div>

          <div style={{ 
            display: "flex", alignItems: "flex-start", gap: "8px", 
            fontSize: "12px", color: "var(--text-secondary)", 
            background: "rgba(245, 158, 11, 0.1)", 
            padding: "12px", borderRadius: "8px", 
            border: "1px solid rgba(245, 158, 11, 0.2)" 
          }}>
            <span style={{ fontSize: "14px", marginTop: "2px" }}>🛡️</span>
            <p style={{ margin: 0, lineHeight: "1.5" }}>
              Your key is saved in <code>localStorage</code> and passed via headers to the backend to authenticate directly with HuggingFace. We do not store your key in any database.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px" }}>
          {!enforced && (
            <button
              onClick={() => handleOpenChange(false)}
              className="btn-secondary"
              style={{ padding: "8px 16px", fontSize: "14px" }}
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleSave}
            style={{
              padding: "8px 16px",
              fontSize: "14px",
              borderRadius: "8px",
              border: "none",
              background: saved ? "#10b981" : "var(--accent-blue)",
              color: "white",
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.2s"
            }}
          >
            {saved ? "Saved!" : "Save Key"}
          </button>
        </div>
      </div>
    </div>
  );
}
