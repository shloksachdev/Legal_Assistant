"use client";

import React, { useEffect, useState } from "react";
import { supabase, isAuthEnabled } from "@/lib/supabase";
import type { User } from "@supabase/supabase-js";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue>({
  user: null,
  loading: true,
  signOut: async () => {},
});

export function useAuth() {
  return React.useContext(AuthContext);
}

export default function SessionWrapper({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!supabase) {
      // No Supabase configured — bypass auth (should not happen with .env.local set)
      setUser({ id: "local-dev", email: "dev@localhost" } as User);
      setLoading(false);
      return;
    }

    // Check current session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Redirect to /login when auth is enabled and there's no user after loading
  useEffect(() => {
    if (
      isAuthEnabled &&
      !loading &&
      !user &&
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login")
    ) {
      window.location.replace("/login");
    }
  }, [user, loading]);

  const handleSignOut = async () => {
    if (supabase) {
      await supabase.auth.signOut();
    }
    window.location.href = "/login";
  };

  // Show nothing while checking auth
  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#050505",
      }}>
        <div style={{
          width: "32px", height: "32px",
          border: "2px solid rgba(255,255,255,0.1)",
          borderTopColor: "#3b82f6",
          borderRadius: "50%",
          animation: "spin 0.6s linear infinite",
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, loading, signOut: handleSignOut }}>
      {children}
    </AuthContext.Provider>
  );
}
