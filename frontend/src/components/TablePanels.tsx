import { Activity, Clock, Dices, Users } from "lucide-react";

import { useSessionStore } from "../store/sessionStore";
import { shortText } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";

export function TablePanels() {
  const characters = useSessionStore((state) => state.characters);
  const runtime = useSessionStore((state) => state.runtime);
  const table = useSessionStore((state) => state.table);
  const turns = useSessionStore((state) => state.turns);
  const clocks = useSessionStore((state) => state.clocks);
  const sceneTrackers = useSessionStore((state) => state.sceneTrackers);
  const rolls = useSessionStore((state) => state.rolls);
  const graph = useSessionStore((state) => state.graph);
  const latestTurn = turns.at(-1);
  const latestRoll = rolls.at(-1);
  return (
    <section className="table-row">
      <div className="table-view panel">
        <header className="panel-header panel-header--compact">
          <div>
            <p className="eyebrow">Table</p>
            <h2>{latestTurn?.scene_id ?? "Current Scene"}</h2>
          </div>
          <Users aria-hidden="true" size={19} />
        </header>
        <div className="play-table">
          <div className="seat-grid">
            {characters.slice(0, 4).map((character) => (
              <div className="seat-token" key={character.character_id}>
                <strong>{character.name}</strong>
                <span>{character.player_id}</span>
              </div>
            ))}
          </div>
          <div className="felt-center">
            <span>{runtime?.mode_stack?.join(" / ") || "table"}</span>
            <strong>
              {latestTurn ? `Turn ${latestTurn.turn_id}` : "No turn"}
            </strong>
            <small>
              {latestRoll
                ? `${latestRoll.outcome} ${latestRoll.total}/${latestRoll.target}`
                : "No roll"}
            </small>
          </div>
        </div>
      </div>
      <div className="turn-summary panel">
        <header className="panel-header panel-header--compact">
          <div>
            <p className="eyebrow">Turn Summary</p>
            <h2>{latestTurn?.speaker ?? "No speaker"}</h2>
          </div>
          <Activity aria-hidden="true" size={19} />
        </header>
        <MarkdownBlock
          content={shortText(latestTurn?.markdown || latestTurn?.prose, 900)}
          emptyLabel="No turns"
          compact
        />
        <div className="meter-grid">
          {clocks.slice(0, 3).map((clock) => (
            <Meter
              key={clock.clock_id}
              label={clock.label}
              max={clock.max}
              value={clock.value}
            />
          ))}
          {sceneTrackers.slice(0, 3).map((tracker) => (
            <Meter
              key={tracker.tracker_id}
              label={tracker.label}
              max={tracker.max}
              value={tracker.value}
            />
          ))}
        </div>
        <div className="table-context">
          <Clock aria-hidden="true" size={16} />
          <span>
            {table.scene?.title ?? table.index?.title ?? "No table file"}
          </span>
          <Dices aria-hidden="true" size={16} />
          <span>{rolls.length} rolls</span>
          <span>{graph?.entities.length ?? 0} entities</span>
          <span>{graph?.edges.length ?? 0} edges</span>
        </div>
      </div>
    </section>
  );
}

function Meter({
  label,
  value,
  max,
}: {
  label: string;
  value: number;
  max: number;
}) {
  return (
    <div className="meter">
      <div className="meter__label">
        <span>{label}</span>
        <strong>
          {value}/{max}
        </strong>
      </div>
      <progress aria-label={label} max={max} value={value} />
    </div>
  );
}
