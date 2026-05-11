import { AlertTriangle, RefreshCcw, Shield } from "lucide-react";
import { useCallback } from "react";

import { sectionLabel } from "../sections";
import {
  selectActiveFiles,
  selectLatestDmTurn,
  useSessionStore,
} from "../store/sessionStore";
import { formatTime, shortText } from "../utils";
import { FileExplorer } from "./FileExplorer";
import { MarkdownBlock } from "./MarkdownBlock";

export function DmPanel() {
  const runtime = useSessionStore((state) => state.runtime);
  const latestDmTurn = useSessionStore(selectLatestDmTurn);
  const explorerFiles = useSessionStore(selectActiveFiles);
  const activeSection = useSessionStore((state) => state.activeSection);
  const selectedFile = useSessionStore((state) => state.selectedFile);
  const databaseError = useSessionStore((state) => state.databaseError);
  const generatedAt = useSessionStore((state) => state.generatedAt);
  const isRefreshing = useSessionStore((state) => state.isPolling);
  const refreshCurrentState = useSessionStore(
    (state) => state.refreshCurrentState,
  );
  const loadFile = useSessionStore((state) => state.loadFile);
  const handleSelectFile = useCallback(
    (path: string) => void loadFile(path),
    [loadFile],
  );
  const latestText =
    latestDmTurn?.markdown || latestDmTurn?.prose || runtime?.summary;
  return (
    <section className="dm-panel panel">
      <header className="panel-header">
        <div>
          <p className="eyebrow">Dungeon Master</p>
          <h1>{runtime?.campaign ?? "Agents of Glass"}</h1>
        </div>
        <div className="header-actions">
          <span>{formatTime(generatedAt)}</span>
          <button
            aria-label="Refresh"
            className="icon-button"
            disabled={isRefreshing}
            onClick={() => void refreshCurrentState()}
            type="button"
          >
            <RefreshCcw aria-hidden="true" size={18} />
          </button>
        </div>
      </header>
      {databaseError && (
        <div className="status-banner">
          <AlertTriangle aria-hidden="true" size={17} />
          <span>{databaseError}</span>
        </div>
      )}
      <div className="dm-panel__body">
        <div className="dm-panel__summary">
          <div className="stat-strip">
            <span>Status: {runtime?.status ?? "unknown"}</span>
            <span>Turn: {runtime?.turn_counter ?? 0}</span>
            <span>Mode: {runtime?.mode_stack?.at(-1) ?? "table"}</span>
          </div>
          <MarkdownBlock
            content={shortText(latestText, 1200)}
            emptyLabel="No DM narrative"
            compact
          />
        </div>
        <div className="dm-panel__notes">
          <div className="selected-file">
            <div className="mini-header">
              <span>{selectedFile?.title ?? "Open Notes"}</span>
              <Shield aria-hidden="true" size={15} />
            </div>
            <MarkdownBlock
              content={selectedFile?.content}
              emptyLabel="Select a note"
              compact
            />
          </div>
          <FileExplorer
            files={explorerFiles}
            limit={7}
            onSelect={handleSelectFile}
            selectedPath={selectedFile?.path}
            title={sectionLabel(activeSection)}
          />
        </div>
      </div>
    </section>
  );
}
