import { AlertTriangle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AgentLanes } from "./components/AgentLanes";
import { ArchiveBrowser } from "./components/ArchiveBrowser";
import { CampaignSelector } from "./components/CampaignSelector";
import { CommandPalette } from "./components/CommandPalette";
import { ContextRail } from "./components/ContextRail";
import { LeftMenu } from "./components/LeftMenu";
import { Scorebug } from "./components/Scorebug";
import { TranscriptCanvas } from "./components/TranscriptCanvas";
import { TurnOutputView } from "./components/TurnOutputView";
import { getConfig } from "./config";
import { useSessionStore } from "./store/sessionStore";

type AppRoute = "live" | "archive" | "output";

function App() {
  const bootstrap = useSessionStore((state) => state.bootstrap);
  const pollLive = useSessionStore((state) => state.pollLive);
  const loadFile = useSessionStore((state) => state.loadFile);
  const error = useSessionStore((state) => state.error);

  const [route, setRoute] = useState<AppRoute>(() => routeFromPath());
  const [commandOpen, setCommandOpen] = useState(false);
  const [jumpTurnId, setJumpTurnId] = useState<number | null>(null);

  useEffect(() => {
    const { pollIntervalMs } = getConfig();
    void bootstrap();
    const handle = window.setInterval(() => void pollLive(), pollIntervalMs);
    return () => window.clearInterval(handle);
  }, [bootstrap, pollLive]);

  useEffect(() => {
    const onPop = () => setRoute(routeFromPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const isCmdK =
        (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (isCmdK) {
        event.preventDefault();
        setCommandOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const navigate = useCallback((next: AppRoute) => {
    const path =
      next === "archive"
        ? "/documents"
        : next === "output"
          ? "/output"
          : "/";
    window.history.pushState({}, "", path);
    setRoute(next);
  }, []);

  const handleJumpTurn = useCallback(
    (turnId: number) => {
      if (route !== "live") {
        navigate("live");
      }
      setJumpTurnId(turnId);
    },
    [navigate, route],
  );

  const handleOpenFile = useCallback(
    (path: string) => {
      if (route !== "archive") {
        navigate("archive");
      }
      void loadFile(path);
    },
    [loadFile, navigate, route],
  );

  return (
    <>
      <main className={`app-shell app-shell--${route}`}>
        <div className="app-nav">
          <LeftMenu
            activeRoute={route}
            onNavigate={navigate}
            onOpenCommand={() => setCommandOpen(true)}
          />
        </div>
        <div className="app-scorebug">
          {route === "live" ? (
            <Scorebug onOpenCommand={() => setCommandOpen(true)} />
          ) : (
            <RouteTopBar
              eyebrow={route === "output" ? "Live tap" : "Echo Ledger"}
              name={route === "output" ? "Turn output" : "Archive"}
              onOpenCommand={() => setCommandOpen(true)}
            />
          )}
        </div>
        <div className="app-stage">
          {error && (
            <div className="status-banner">
              <AlertTriangle aria-hidden="true" size={14} />
              <span>{error}</span>
            </div>
          )}
          {route === "live" && (
            <TranscriptCanvas
              jumpTurnId={jumpTurnId}
              onJumpHandled={() => setJumpTurnId(null)}
            />
          )}
          {route === "archive" && <ArchiveBrowser error={error} />}
          {route === "output" && <TurnOutputView />}
        </div>
        {route === "live" && (
          <>
            <div className="app-rail">
              <ContextRail onJumpTurn={handleJumpTurn} />
            </div>
            <div className="app-lanes">
              <AgentLanes onJumpTurn={handleJumpTurn} />
            </div>
          </>
        )}
      </main>
      <CommandPalette
        isOpen={commandOpen}
        onClose={() => setCommandOpen(false)}
        onGoTo={navigate}
        onJumpTurn={handleJumpTurn}
        onOpenFile={handleOpenFile}
      />
    </>
  );
}

function RouteTopBar({
  eyebrow,
  name,
  onOpenCommand,
}: {
  eyebrow: string;
  name: string;
  onOpenCommand: () => void;
}) {
  return (
    <div className="scorebug">
      <CampaignSelector />
      <div className="scorebug__scene">
        <span className="scorebug__scene-mode">{eyebrow}</span>
        <span className="scorebug__scene-id">{name}</span>
      </div>
      <div className="scorebug__clocks" />
      <button
        aria-label="Open command palette"
        className="scorebug__refresh"
        onClick={onOpenCommand}
        type="button"
        title="⌘K"
      >
        <span aria-hidden="true" style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>
          ⌘K
        </span>
      </button>
    </div>
  );
}

function routeFromPath(): AppRoute {
  const path = window.location.pathname;
  if (path.startsWith("/output")) return "output";
  if (path.startsWith("/documents")) return "archive";
  return "live";
}

export default App;
