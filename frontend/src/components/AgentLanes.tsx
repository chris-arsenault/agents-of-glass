import { useMemo } from "react";

import { AGENT_DISPLAY, sigilFor, toneFor } from "../agentChroma";
import type { AgentTone } from "../agentChroma";
import {
  usePlayerIds,
  useSessionStore,
} from "../store/sessionStore";
import type { TurnRecord } from "../types";

interface LanesProps {
  onJumpTurn: (turnId: number) => void;
}

interface LaneTick {
  turnId: number;
  position: number; // 0..1
  heavy: boolean;
  scene?: string | null;
  timestamp: number;
}

interface LaneData {
  tone: AgentTone;
  playerId: string;
  display: string;
  sigil: string;
  ticks: LaneTick[];
  status: {
    hp?: string;
    momentum?: number;
    mode?: string;
  };
  isActive: boolean;
}

export function AgentLanes({ onJumpTurn }: LanesProps) {
  const turns = useSessionStore((state) => state.turns);
  const playerIds = usePlayerIds();
  const characters = useSessionStore((state) => state.characters);

  const allAgents: string[] = useMemo(
    () => ["mara", ...playerIds],
    [playerIds],
  );

  const range = useMemo(() => {
    if (turns.length === 0) {
      return { min: 0, max: 1 };
    }
    const stamps = turns
      .map((t) => Date.parse(t.created_at || t.ts))
      .filter((v) => Number.isFinite(v));
    if (stamps.length === 0) {
      return { min: 0, max: 1 };
    }
    return {
      min: Math.min(...stamps),
      max: Math.max(...stamps),
    };
  }, [turns]);

  const span = Math.max(1, range.max - range.min);
  const lastTurn = turns.at(-1);
  const lastSpeaker = lastTurn?.speaker ?? null;

  const lanes: LaneData[] = useMemo(
    () =>
      allAgents.map((agent) => {
        const tone = toneFor(agent);
        const display = AGENT_DISPLAY[tone] ?? agent;
        const sigil = sigilFor(display);
        const character =
          characters.find((c) => c.player_id === agent) ??
          (agent === "mara" ? undefined : undefined);
        const ticks = turnsForAgent(turns, agent).map((turn) => {
          const ts = Date.parse(turn.created_at || turn.ts) || range.min;
          const position = Math.max(0, Math.min(1, (ts - range.min) / span));
          return {
            turnId: turn.turn_id,
            position,
            heavy: turn.event_summaries.length > 0,
            scene: turn.scene_id,
            timestamp: ts,
          };
        });
        return {
          tone,
          playerId: agent,
          display,
          sigil,
          ticks,
          status: {
            hp: character
              ? `${character.hp.current}/${character.hp.max}`
              : undefined,
            momentum: character?.momentum.current,
            mode: ticks.at(-1)?.scene ?? undefined,
          },
          isActive: lastSpeaker === agent,
        };
      }),
    [allAgents, characters, lastSpeaker, range.min, span, turns],
  );

  return (
    <section className="lanes" aria-label="Agent activity">
      <header className="lanes__head">
        <strong>Agent lanes</strong>
        <span>—</span>
        <span>{turns.length} turns visible</span>
        <span className="lanes__head-spacer" />
        <span className="lanes__head-meta">
          click a tick to jump
        </span>
      </header>
      <div className="lanes__body">
        {lanes.map((lane) => (
          <div
            className={`lane${lane.isActive ? " is-active" : ""}`}
            data-tone={lane.tone}
            key={lane.playerId}
          >
            <div className="lane__name">
              <span className="lane__dot" aria-hidden="true" />
              <span>{lane.display}</span>
            </div>
            <span className="lane__sigil" aria-hidden="true">{lane.sigil}</span>
            <div className="lane__track">
              {lane.ticks.map((tick) => (
                <button
                  aria-label={`Turn ${tick.turnId}`}
                  className={`lane__tick${tick.heavy ? " lane__tick--heavy" : ""}`}
                  key={`${lane.playerId}-${tick.turnId}`}
                  onClick={() => onJumpTurn(tick.turnId)}
                  style={{ left: `${tick.position * 100}%` }}
                  title={`Turn ${tick.turnId}${tick.scene ? " · " + tick.scene : ""}`}
                  type="button"
                />
              ))}
            </div>
            <div className="lane__status">
              {lane.status.hp && (
                <span className="lane__status-pair">
                  <span className="lane__status-key">hp</span>
                  <span className="lane__status-val">{lane.status.hp}</span>
                </span>
              )}
              {lane.status.momentum !== undefined && (
                <span className="lane__status-pair">
                  <span className="lane__status-key">m</span>
                  <span className="lane__status-val">{lane.status.momentum}</span>
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function turnsForAgent(turns: TurnRecord[], agent: string): TurnRecord[] {
  return turns.filter((turn) =>
    agent === "mara"
      ? turn.role === "dm" || turn.speaker === "dm" || turn.speaker === "mara"
      : turn.speaker === agent,
  );
}

