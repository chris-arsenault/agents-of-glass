import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ScrollText } from "lucide-react";
import { useMemo } from "react";

import { sigilFor, toneFor, AGENT_DISPLAY } from "../agentChroma";
import type { TranscriptTurnEntry } from "../transcriptModel";
import { formatTime } from "../utils";
import { MechanicChip } from "./MechanicChip";

const markdownPlugins = [remarkGfm];

interface TurnCardProps {
  entry: TranscriptTurnEntry;
  characterName?: string | null;
  fresh?: boolean;
  onJump?: () => void;
}

export function TurnCard({ entry, characterName, fresh, onJump }: TurnCardProps) {
  const { turn, prose, mechanics } = entry;
  const tone = toneFor(turn.speaker);
  const sigil = sigilFor(turn.speaker);
  const personLabel = AGENT_DISPLAY[tone] ?? turn.speaker.toUpperCase();
  const time = formatTime(turn.created_at || turn.ts);

  const titleLine = useMemo(() => {
    if (turn.role === "dm") {
      return characterName ?? "Mara";
    }
    return characterName ?? "—";
  }, [characterName, turn.role]);

  return (
    <article
      className={`turn-card${fresh ? " is-fresh" : ""}`}
      data-tone={tone}
      data-turn-id={turn.turn_id}
      onDoubleClick={onJump}
    >
      <span className="turn-card__stripe" aria-hidden="true" />
      <div className="turn-card__body">
        <header className="turn-card__head">
          <span className="turn-card__sigil" aria-hidden="true">
            {sigil}
          </span>
          <span className="turn-card__person">{personLabel}</span>
          {titleLine && (
            <>
              <span className="turn-card__arrow" aria-hidden="true">
                ─►
              </span>
              <span className="turn-card__character">{titleLine}</span>
            </>
          )}
          <span className="turn-card__meta">
            <span>Turn {turn.turn_id}</span>
            <span className="turn-card__meta-divider" />
            <span>{turn.mode}</span>
            {turn.scene_id && (
              <>
                <span className="turn-card__meta-divider" />
                <span>{turn.scene_id}</span>
              </>
            )}
            <span className="turn-card__meta-divider" />
            <ScrollText aria-hidden="true" size={11} />
            <span>{time}</span>
          </span>
        </header>

        {prose.map((block, idx) =>
          block.kind === "ic" ? (
            <div className="turn-card__prose" key={`ic-${idx}`}>
              <ReactMarkdown remarkPlugins={markdownPlugins}>
                {block.body}
              </ReactMarkdown>
            </div>
          ) : (
            <aside className="turn-card__ooc" key={`ooc-${idx}`}>
              <div className="turn-card__ooc-body">
                {block.speaker && (
                  <strong style={{ fontStyle: "normal", marginRight: 6 }}>
                    {block.speaker}:
                  </strong>
                )}
                {block.body}
              </div>
            </aside>
          ),
        )}

        {mechanics.length > 0 && (
          <div className="turn-card__mechanics">
            {mechanics.map((event, idx) => (
              <MechanicChip
                event={event}
                fresh={fresh}
                key={`${event.kind}-${idx}-${event.raw.slice(0, 24)}`}
              />
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
