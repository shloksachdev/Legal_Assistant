"use client";

import React, { useState, useEffect } from "react";
import { supabase, isAuthEnabled } from "@/lib/supabase";

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Redirect to app if already signed in
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) window.location.href = "/";
    });
  }, []);

  const handleGoogleLogin = async () => {
    if (!supabase) return;
    setIsLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/` },
    });
    if (error) {
      setError(error.message);
      setIsLoading(false);
    }
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    if (!email.trim() || !password.trim()) {
      setError("Enter both email and password.");
      return;
    }
    setIsLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    if (error) {
      setError(error.message);
      setIsLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      background: "#050505",
      backgroundImage:
        "radial-gradient(circle at 15% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 40%), " +
        "radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.08) 0%, transparent 40%)",
      fontFamily: "'Inter', sans-serif",
      padding: "0 20px",
    }}>
      {/* Logo */}
      <div style={{
        width: "72px", height: "72px", borderRadius: "22px",
        background: "linear-gradient(135deg, #3b82f6, #bc8cff)",
        display: "flex", alignItems: "center", justifyContent: "center",
        marginBottom: "24px",
        boxShadow: "0 8px 32px rgba(59,130,246,0.3)",
      }}>
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L12 22M12 4L4 4M12 4L20 4M4 4L2 12C2 13.1046 2.89543 14 4 14C5.10457 14 6 13.1046 6 12L4 4ZM20 4L18 12C18 13.1046 18.8954 14 20 14C21.1046 14 22 13.1046 22 12L20 4Z"
            stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M9 22H15" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>

      {/* Title */}
      <h1 style={{
        fontSize: "36px", fontWeight: 800, color: "#f8fafc",
        letterSpacing: "-0.5px", marginBottom: "4px", textAlign: "center",
      }}>
        TempLex <span style={{ color: "#3b82f6" }}>GraphRAG</span>
      </h1>
      <p style={{
        fontSize: "16px", color: "#64748b", marginBottom: "40px", textAlign: "center",
      }}>
        AI-Powered Temporal Legal Reasoning
      </p>

      {/* Login Card */}
      <div style={{
        width: "100%", maxWidth: "440px",
        background: "rgba(255,255,255,0.03)",
        backdropFilter: "blur(12px)",
        border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: "32px",
        padding: "40px 36px",
        boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
      }}>
        {/* Error message */}
        {error && (
          <div style={{
            padding: "12px 16px", marginBottom: "20px",
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: "12px",
            fontSize: "13px", color: "#ef4444",
          }}>
            ⚠️ {error}
          </div>
        )}

        {/* Google Sign In Button */}
        <button
          type="button"
          onClick={handleGoogleLogin}
          disabled={isLoading}
          style={{
            width: "100%", display: "flex", alignItems: "center", justifyContent: "center",
            gap: "12px", padding: "16px 24px",
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: "16px",
            cursor: isLoading ? "not-allowed" : "pointer",
            opacity: isLoading ? 0.6 : 1,
            transition: "all 0.2s ease",
            color: "#f8fafc", fontSize: "16px", fontWeight: 600,
            fontFamily: "'Inter', sans-serif",
          }}
          onMouseEnter={(e) => {
            if (!isLoading) {
              e.currentTarget.style.background = "rgba(255,255,255,0.08)";
              e.currentTarget.style.borderColor = "rgba(59,130,246,0.4)";
              e.currentTarget.style.transform = "translateY(-1px)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.05)";
            e.currentTarget.style.borderColor = "rgba(255,255,255,0.12)";
            e.currentTarget.style.transform = "translateY(0)";
          }}
        >
          {isLoading ? (
            <div style={{
              width: "20px", height: "20px",
              border: "2px solid rgba(255,255,255,0.2)",
              borderTopColor: "#3b82f6",
              borderRadius: "50%",
              animation: "spin 0.6s linear infinite",
            }} />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
          )}
          {isLoading ? "Signing in..." : "Continue with Google"}
        </button>

        {/* Divider */}
        <div style={{
          display: "flex", alignItems: "center", margin: "28px 0 22px 0",
          gap: "16px",
        }}>
          <div style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.08)" }} />
          <span style={{ fontSize: "12px", color: "#64748b", fontWeight: 500 }}>SECURE LOGIN</span>
          <div style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.08)" }} />
        </div>

        {/* Email / Password Login */}
        <form onSubmit={handleEmailLogin} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <label style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 600, letterSpacing: "0.4px" }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              style={{
                width: "100%",
                padding: "14px 16px",
                borderRadius: "14px",
                border: "1px solid rgba(255,255,255,0.10)",
                background: "rgba(255,255,255,0.03)",
                color: "#f8fafc",
                outline: "none",
                fontSize: "14px",
              }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <label style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 600, letterSpacing: "0.4px" }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              style={{
                width: "100%",
                padding: "14px 16px",
                borderRadius: "14px",
                border: "1px solid rgba(255,255,255,0.10)",
                background: "rgba(255,255,255,0.03)",
                color: "#f8fafc",
                outline: "none",
                fontSize: "14px",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              width: "100%",
              marginTop: "4px",
              padding: "14px 16px",
              borderRadius: "16px",
              border: "1px solid rgba(59,130,246,0.25)",
              background: "linear-gradient(135deg, rgba(59,130,246,0.95), rgba(139,92,246,0.95))",
              color: "white",
              fontSize: "15px",
              fontWeight: 700,
              cursor: isLoading ? "not-allowed" : "pointer",
              opacity: isLoading ? 0.7 : 1,
              boxShadow: "0 10px 24px rgba(59,130,246,0.18)",
            }}
          >
            {isLoading ? "Signing in..." : "Continue with Email"}
          </button>
        </form>

        {/* Info badges */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "26px" }}>
          {[
            { icon: "🔍", label: "Semantic vector search", desc: "Find laws by meaning, not keywords" },
            { icon: "📅", label: "Temporal reasoning", desc: "See what the law was on any date" },
            { icon: "🔗", label: "Causal graph traversal", desc: "Trace how laws evolved over time" },
          ].map((item) => (
            <div key={item.label} style={{
              display: "flex", gap: "12px", alignItems: "center",
              padding: "12px 16px",
              background: "rgba(255,255,255,0.02)",
              borderRadius: "12px",
              border: "1px solid rgba(255,255,255,0.05)",
            }}>
              <span style={{ fontSize: "18px" }}>{item.icon}</span>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "#f8fafc" }}>{item.label}</div>
                <div style={{ fontSize: "11px", color: "#64748b" }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <p style={{ fontSize: "11px", color: "#475569", marginTop: "32px", textAlign: "center" }}>
        Powered by KuzuDB • LangChain • Hugging Face
      </p>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
