"use client";

import React, { useState, useEffect } from "react";

interface ScopeOptions {
  domains: string[];
  jurisdictions: string[];
  date_range: { earliest: string; latest: string };
}

interface ScopeSelectorProps {
  apiBase: string;
  onStart: (scope: { reference_date: string; domains: string[]; jurisdictions: string[] }) => void;
}

export default function ScopeSelector({ apiBase, onStart }: ScopeSelectorProps) {
  const [options, setOptions] = useState<ScopeOptions | null>(null);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split("T")[0]);
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [selectedJurisdictions, setSelectedJurisdictions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchOptions() {
      try {
        const res = await fetch(`${apiBase}/api/scope/options`);
        if (res.ok) {
          const data = await res.json();
          setOptions(data);
          setSelectedDomains(data.domains); // Default all checked
          setSelectedJurisdictions(data.jurisdictions); // Default all checked
        }
      } catch (err) {
        console.error("Failed to fetch scope options", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchOptions();
  }, [apiBase]);

  const handleToggleDomain = (domain: string) => {
    setSelectedDomains(prev => 
      prev.includes(domain) ? prev.filter(d => d !== domain) : [...prev, domain]
    );
  };

  const handleToggleJurisdiction = (j: string) => {
    setSelectedJurisdictions(prev =>
      prev.includes(j) ? prev.filter(item => item !== j) : [...prev, j]
    );
  };

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "400px" }}>
        <div className="spinner" style={{ width: "32px", height: "32px" }} />
      </div>
    );
  }

  return (
    <div className="glass-card animate-fade-in" style={{
      maxWidth: "500px",
      margin: "40px auto",
      padding: "32px",
      borderRadius: "32px",
      display: "flex",
      flexDirection: "column",
      gap: "24px",
      boxShadow: "0 20px 50px rgba(0,0,0,0.3)",
    }}>
      <div style={{ textAlign: "center" }}>
        <h2 style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "8px" }}>
          Configure Session Scope
        </h2>
        <p style={{ fontSize: "14px", color: "var(--text-muted)" }}>
          Set your temporal and topical boundaries for this legal research session.
        </p>
      </div>

      {/* Date Picker */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--accent-blue)", textTransform: "uppercase", letterSpacing: "1px" }}>
          View law as of
        </label>
        <input 
          type="date"
          value={selectedDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          style={{
            width: "100%",
            padding: "12px 16px",
            borderRadius: "12px",
            background: "var(--bg-secondary)",
            border: "1px solid var(--border-default)",
            color: "var(--text-primary)",
            fontSize: "16px",
            outline: "none",
          }}
        />
        <p style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          Provisions active on this date will be ranked higher.
        </p>
      </div>

      {/* Domains */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--accent-blue)", textTransform: "uppercase", letterSpacing: "1px" }}>
          Legal Domains
        </label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {options?.domains.map(domain => {
            const isSelected = selectedDomains.includes(domain);
            return (
              <button
                key={domain}
                onClick={() => handleToggleDomain(domain)}
                style={{
                  padding: "8px 16px",
                  borderRadius: "9999px",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  background: isSelected ? "var(--accent-blue)" : "var(--bg-secondary)",
                  color: isSelected ? "white" : "var(--text-secondary)",
                  border: isSelected ? "1px solid var(--accent-blue)" : "1px solid var(--border-default)",
                }}
              >
                {domain.charAt(0).toUpperCase() + domain.slice(1)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Jurisdictions */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--accent-blue)", textTransform: "uppercase", letterSpacing: "1px" }}>
          Jurisdictions
        </label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {options?.jurisdictions.map(j => {
            const isSelected = selectedJurisdictions.includes(j);
            return (
              <button
                key={j}
                onClick={() => handleToggleJurisdiction(j)}
                style={{
                  padding: "8px 16px",
                  borderRadius: "9999px",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  background: isSelected ? "var(--accent-green)" : "var(--bg-secondary)",
                  color: isSelected ? "white" : "var(--text-secondary)",
                  border: isSelected ? "1px solid var(--accent-green)" : "1px solid var(--border-default)",
                }}
              >
                {j}
              </button>
            );
          })}
        </div>
      </div>

      <button
        onClick={() => onStart({ reference_date: selectedDate, domains: selectedDomains, jurisdictions: selectedJurisdictions })}
        className="btn-primary"
        style={{
          marginTop: "12px",
          padding: "16px",
          borderRadius: "16px",
          fontSize: "16px",
          fontWeight: 700,
          background: "linear-gradient(135deg, var(--accent-blue), #bc8cff)",
          border: "none",
          color: "white",
          cursor: "pointer",
          boxShadow: "0 8px 20px rgba(88,166,255,0.3)",
        }}
      >
        Start Research Session →
      </button>

      <div style={{ fontSize: "11px", color: "var(--text-muted)", textAlign: "center", fontStyle: "italic" }}>
        * Scope affects ranking. All history and cross-domain data remains accessible.
      </div>
    </div>
  );
}
