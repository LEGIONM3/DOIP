import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { SideNav } from "./SideNav";
import { TopBar } from "./TopBar";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { CommandPalette } from "./CommandPalette";
import { LoginScreen } from "./LoginScreen";
import { AiDrawer } from "./AiDrawer";
import { DisconnectBanner } from "@/components/doip/DisconnectBanner";
import { ShortcutSheet } from "@/components/doip/ShortcutSheet";
import { simStore, useSim } from "@/sim/store";
import { contextStore, useOperationalContext } from "@/sim/contextStore";
import { useKeyboard } from "@/hooks/useKeyboard";
import { WORKSPACES } from "@/lib/workspaces";

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const role = useSim((s) => s.role);
  const [collapsed, setCollapsed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  // Sync with context store AI state
  const contextAiOpen = useOperationalContext((s) => s.aiDrawerOpen);
  const [aiOpen, setAiOpen] = useState(false);

  useEffect(() => {
    if (contextAiOpen) {
      setAiOpen(true);
    }
  }, [contextAiOpen]);

  const handleToggleAi = () => {
    setAiOpen((prev) => {
      const next = !prev;
      contextStore.setAiDrawerOpen(next);
      return next;
    });
  };

  // Emit custom events for sub-components
  const emitFollow = () => window.dispatchEvent(new CustomEvent("doip:follow-toggle"));
  const emitFocusFeed = () => window.dispatchEvent(new CustomEvent("doip:focus-feed"));

  // Global keyboard shortcuts
  useKeyboard({
    " ": () => {
      if (role === "viewer") return;
      const s = simStore.getState();
      if (s.status === "RUNNING") simStore.pause();
      else if (s.status === "PAUSED") simStore.resume();
    },
    F: emitFollow,
    f: emitFollow,
    E: emitFocusFeed,
    e: emitFocusFeed,
    "?": () => setShortcutsOpen((o) => !o),
  });

  // Alt + ArrowLeft/ArrowRight for backward/forward page routing, Alt + 1..7 for workspace jumping
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.key === "ArrowLeft") {
        e.preventDefault();
        window.history.back();
      } else if (e.altKey && e.key === "ArrowRight") {
        e.preventDefault();
        window.history.forward();
      } else if (e.altKey && e.key >= "1" && e.key <= "7") {
        const index = parseInt(e.key, 10) - 1;
        const ws = WORKSPACES[index];
        if (ws && (ws.id !== "governance" || role === "admin")) {
          e.preventDefault();
          contextStore.setWorkspace(ws.id);
          void navigate({ to: ws.defaultRoute });
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, role]);

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    simStore.hydrateSession();
  }, []);

  if (!mounted) {
    return <div className="min-h-screen bg-background text-foreground" />;
  }

  if (!role) return <LoginScreen />;

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      {/* Role-aware Sidebar with 7 Workspaces */}
      <SideNav collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} role={role} />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Persistent synthetic-exercise banner */}
        <div className="doip-exercise-banner shrink-0" aria-hidden>
          {Array.from({ length: 24 }).map((_, i) => (
            <span key={i} className="px-2">
              EXERCISE — SYNTHETIC DATA
            </span>
          ))}
        </div>

        {/* Offline Disconnect Banner */}
        <DisconnectBanner />

        {/* Global TopBar */}
        <TopBar
          onOpenPalette={() => setPaletteOpen(true)}
          onToggleAi={handleToggleAi}
          aiOpen={aiOpen}
          onOpenShortcuts={() => setShortcutsOpen((o) => !o)}
        />

        {/* Workspace Context Header & Secondary Navigation */}
        <WorkspaceHeader />

        {/* Workspace Viewport & Contextual Intelligence Drawer */}
        <div className="flex min-h-0 flex-1">
          <main className="doip-ground min-h-0 min-w-0 flex-1 overflow-auto">{children}</main>
          {aiOpen && (
            <AiDrawer
              onClose={() => {
                setAiOpen(false);
                contextStore.setAiDrawerOpen(false);
              }}
            />
          )}
        </div>

        {/* Persistent Compliance Footer */}
        <footer className="shrink-0 border-t border-border bg-surface px-3 py-1 text-[10px] text-muted-foreground">
          Training &amp; simulation platform. All data is synthetic. Not for operational military use.
        </footer>
      </div>

      {/* Global Command Palette */}
      <CommandPalette open={paletteOpen} setOpen={setPaletteOpen} />

      {/* Keyboard Shortcuts Sheet Overlay */}
      <ShortcutSheet open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}
