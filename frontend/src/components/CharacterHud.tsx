import { Dice5, Flame, HeartPulse, Scaling } from "lucide-react";

import { AGENT_DISPLAY, sigilFor, toneFor } from "../agentChroma";
import {
  selectCharacterForPlayer,
  selectLatestRollForPlayer,
  useSessionStore,
} from "../store/sessionStore";
import { progressPercent } from "../utils";

interface HudProps {
  playerId: string;
  onOpen?: (playerId: string) => void;
}

export function CharacterHud({ playerId, onOpen }: HudProps) {
  const character = useSessionStore((state) =>
    selectCharacterForPlayer(state, playerId),
  );
  const latestRoll = useSessionStore((state) =>
    selectLatestRollForPlayer(state, playerId),
  );
  const tone = toneFor(playerId);
  const sigil = sigilFor(playerId);
  const hpPercent = character
    ? progressPercent(character.hp.current, character.hp.max)
    : 0;
  const hpLow = hpPercent <= 35;

  return (
    <button
      className="hud"
      data-tone={tone}
      onClick={() => onOpen?.(playerId)}
      type="button"
    >
      <div className="hud__head">
        <span className="hud__sigil" aria-hidden="true">{sigil}</span>
        <div className="hud__name">
          <span className="hud__person">{AGENT_DISPLAY[tone] ?? playerId}</span>
          <span className="hud__character">{character?.name ?? "Unassigned"}</span>
        </div>
      </div>
      {character && (
        <div className="hud__sub">
          {character.archetype}
          {character.culture ? ` · ${character.culture}` : ""}
        </div>
      )}
      <div className="hud__stats">
        <div
          className="hud-stat hud-stat--hp"
          data-pct-low={hpLow ? "true" : "false"}
        >
          <HeartPulse aria-hidden="true" size={11} />
          <span className="hud-stat__bar">
            <span
              className="hud-stat__bar-fill"
              style={{ width: `${hpPercent}%` }}
            />
          </span>
          <span className="hud-stat__val">
            {character ? `${character.hp.current}/${character.hp.max}` : "—"}
          </span>
        </div>
        <div className="hud-stat">
          <Flame aria-hidden="true" size={11} />
          <span className="hud-stat__label">Momentum</span>
          <span className="hud-stat__val">{character?.momentum.current ?? "—"}</span>
        </div>
        <div className="hud-stat">
          <Scaling aria-hidden="true" size={11} />
          <span className="hud-stat__label">Lvl</span>
          <span className="hud-stat__val">{character?.level ?? "—"}</span>
        </div>
        <div className="hud-stat">
          <Dice5 aria-hidden="true" size={11} />
          <span className="hud-stat__label">XP</span>
          <span className="hud-stat__val">{character?.xp ?? "—"}</span>
        </div>
      </div>
      {latestRoll && (
        <div className="hud__roll">
          <Dice5 aria-hidden="true" size={11} />
          <span className="hud__roll-skill">
            {latestRoll.skill} + {latestRoll.attribute}
          </span>
          <span className="hud__roll-total">{latestRoll.total}</span>
        </div>
      )}
    </button>
  );
}
