import { Eye, User } from "lucide-react";

import {
  selectCharacterForPlayer,
  selectFilesForPlayer,
  selectLatestRollForPlayer,
  selectLatestTurnForPlayer,
  selectTarotForPlayer,
  useSessionStore,
} from "../store/sessionStore";
import { shortText } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";

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
  const files = useSessionStore((state) =>
    selectFilesForPlayer(state, playerId),
  );
  const loadFile = useSessionStore((state) => state.loadFile);
  return (
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
          HP {character ? `${character.hp.current}/${character.hp.max}` : "n/a"}
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
        {files.slice(0, 3).map((file) => (
          <button
            key={file.path}
            onClick={() => void loadFile(file.path)}
            type="button"
          >
            <Eye aria-hidden="true" size={14} />
            <span>{file.title || file.name}</span>
          </button>
        ))}
      </div>
    </article>
  );
}
