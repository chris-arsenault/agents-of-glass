import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

import { DmPanel } from "./components/DmPanel";
import { DocumentBrowser } from "./components/DocumentBrowser";
import { LeftMenu } from "./components/LeftMenu";
import { MessageLog } from "./components/MessageLog";
import { PlayerRow } from "./components/PlayerRow";
import { TablePanels } from "./components/TablePanels";
import { getConfig } from "./config";
import { useSessionStore } from "./store/sessionStore";

type AppRoute = "live" | "documents";

function App() {
  const bootstrap = useSessionStore((state) => state.bootstrap);
  const pollLive = useSessionStore((state) => state.pollLive);
  const error = useSessionStore((state) => state.error);
  const [route, setRoute] = useState<AppRoute>(() => routeFromPath());

  useEffect(() => {
    const { pollIntervalMs } = getConfig();
    void bootstrap();
    const handle = window.setInterval(() => void pollLive(), pollIntervalMs);
    return () => window.clearInterval(handle);
  }, [bootstrap, pollLive]);

  useEffect(() => {
    const handlePopState = () => setRoute(routeFromPath());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(nextRoute: AppRoute) {
    const path = nextRoute === "documents" ? "/documents" : "/";
    window.history.pushState({}, "", path);
    setRoute(nextRoute);
  }

  return (
    <main className={`app-shell app-shell--${route}`}>
      <LeftMenu activeRoute={route} onNavigate={navigate} />
      {route === "documents" ? (
        <DocumentBrowser error={error} />
      ) : (
        <>
          <div className="main-stage">
            {error && <StatusBanner message={error} />}
            <DmPanel />
            <TablePanels />
            <PlayerRow />
          </div>
          <MessageLog />
        </>
      )}
    </main>
  );
}

function routeFromPath(): AppRoute {
  return window.location.pathname.startsWith("/documents")
    ? "documents"
    : "live";
}

function StatusBanner({ message }: { message: string }) {
  return (
    <div className="status-banner status-banner--global">
      <AlertTriangle aria-hidden="true" size={17} />
      <span>{message}</span>
    </div>
  );
}

export default App;
