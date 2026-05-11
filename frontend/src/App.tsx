import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { DmPanel } from "./components/DmPanel";
import { LeftMenu } from "./components/LeftMenu";
import { MessageLog } from "./components/MessageLog";
import { PlayerRow } from "./components/PlayerRow";
import { TablePanels } from "./components/TablePanels";
import { getConfig } from "./config";
import { useSessionStore } from "./store/sessionStore";

function App() {
  const bootstrap = useSessionStore((state) => state.bootstrap);
  const pollLive = useSessionStore((state) => state.pollLive);
  const error = useSessionStore((state) => state.error);

  useEffect(() => {
    const { pollIntervalMs } = getConfig();
    void bootstrap();
    const handle = window.setInterval(() => void pollLive(), pollIntervalMs);
    return () => window.clearInterval(handle);
  }, [bootstrap, pollLive]);

  return (
    <main className="app-shell">
      <LeftMenu />
      <div className="main-stage">
        {error && <StatusBanner message={error} />}
        <DmPanel />
        <TablePanels />
        <PlayerRow />
      </div>
      <MessageLog />
    </main>
  );
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
