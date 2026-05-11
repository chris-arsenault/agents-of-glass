import { Eye, User } from "lucide-react";
import { useCallback, useMemo, useState, type MouseEvent } from "react";

import {
  selectCharacterForPlayer,
  selectLatestRollForPlayer,
  selectLatestTurnForPlayer,
  selectTarotForPlayer,
  useSessionStore,
} from "../store/sessionStore";
import type { FileEntry } from "../types";
import { fileMatches, shortText } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";
import { Modal } from "./Modal";

interface PlayerColumnProps {
  playerId: string;
}

export function PlayerColumn({ playerId }: PlayerColumnProps) {
  const character = useSessionStore((state) =>
    selectCharacterForPlayer(state, playerId),
  );
  const latestTurn = useSessionStore((state) =>
    selectLatestTurnForPlayer(state, playerId),
  );
  const latestRoll = useSessionStore((state) =>
    selectLatestRollForPlayer(state, playerId),
  );
  const tarot = useSessionStore((state) =>
    selectTarotForPlayer(state, playerId),
  );
  const fileLists = useSessionStore((state) => state.fileLists);
  const files = useMemo(() => {
    const terms = [playerId, character?.character_id, character?.name]
      .filter((value): value is string => Boolean(value))
      .map((value) => value.toLowerCase());
    return Object.values(fileLists)
      .flat()
      .filter((file) => fileMatches(file, terms));
  }, [character?.character_id, character?.name, fileLists, playerId]);
  const quickFiles = useMemo(() => {
    const preferredPaths = [
      `players/${playerId}/notes/index.md`,
      `players/${playerId}/persona.md`,
      `players/${playerId}/public/character.md`,
    ];
    const preferred = preferredPaths
      .map((path) => files.find((file) => file.path === path))
      .filter((file): file is FileEntry => Boolean(file));
    if (preferred.length >= 3) {
      return preferred;
    }
    const extras = files.filter(
      (file) => !preferredPaths.includes(file.path),
    );
    return [...preferred, ...extras].slice(0, 3);
  }, [files, playerId]);
  const loadFile = useSessionStore((state) => state.loadFile);
  const selectedFile = useSessionStore((state) => state.selectedFile);
  const isFileLoading = useSessionStore((state) => state.isFileLoading);
  const [modalPath, setModalPath] = useState<string | null>(null);
  const modalSource = files.find((file) => file.path === modalPath);
  const modalFile = selectedFile?.path === modalPath ? selectedFile : null;
  const notesIndexPath = `players/${playerId}/notes/index.md`;

  const openQuickFile = useCallback((path: string) => {
    if (path === notesIndexPath) {
      const params = new URLSearchParams({
        prefix: `players/${playerId}/notes`,
      });
      window.history.pushState({}, "", `/documents?${params.toString()}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
      return;
    }
    setModalPath(path);
    void loadFile(path);
  }, [loadFile, notesIndexPath, playerId]);
  const handleQuickFileClick = useCallback(
    (event: MouseEvent<HTMLButtonElement>) => {
      const path = event.currentTarget.dataset.path;
      if (path) {
        openQuickFile(path);
      }
    },
    [openQuickFile],
  );
  const closeModal = useCallback(() => setModalPath(null), []);

  return (
    <>
      <article className="player-column panel">
        <header className="player-column__header">
          <div>
            <p className="eyebrow">{playerId}</p>
            <h3>{character?.name ?? "Unassigned"}</h3>
          </div>
          <User aria-hidden="true" size={18} />
        </header>
        <div className="player-stats">
          <span>
            HP{" "}
            {character ? `${character.hp.current}/${character.hp.max}` : "n/a"}
          </span>
          <span>Momentum {character?.momentum.current ?? "n/a"}</span>
          <span>Level {character?.level ?? "n/a"}</span>
        </div>
        <p className="character-line">
          {character?.archetype ?? "No character"} -{" "}
          {character?.culture ?? "Unknown"}
        </p>
        <MarkdownBlock
          content={shortText(latestTurn?.markdown || latestTurn?.prose, 650)}
          emptyLabel="No narrative"
          compact
        />
        <div className="player-column__detail">
          <span>
            {tarot ? `${tarot.card_name}: ${tarot.influence}` : "No tarot"}
          </span>
          <span>
            {latestRoll ? `${latestRoll.skill} ${latestRoll.total}` : "No roll"}
          </span>
        </div>
        <div className="quick-files">
          {quickFiles.map((file) => (
            <button
              data-path={file.path}
              key={file.path}
              onClick={handleQuickFileClick}
              type="button"
            >
              <Eye aria-hidden="true" size={14} />
              <span>{file.title || file.name}</span>
            </button>
          ))}
        </div>
      </article>
      <Modal
        isOpen={modalPath !== null}
        onClose={closeModal}
        subtitle={modalPath}
        title={modalFile?.title ?? modalSource?.title ?? "Player file"}
      >
        <MarkdownBlock
          content={modalFile?.content}
          emptyLabel={isFileLoading ? "Loading file" : "No file content"}
        />
      </Modal>
    </>
  );
}
