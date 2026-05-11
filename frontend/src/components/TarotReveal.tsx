import { Sparkles } from "lucide-react";

import { AGENT_DISPLAY, toneFor } from "../agentChroma";
import type { TranscriptTarotEntry } from "../transcriptModel";

export function TarotReveal({ entry }: { entry: TranscriptTarotEntry }) {
  const tone = toneFor(entry.tarot.actor);
  const actorLabel = AGENT_DISPLAY[tone] ?? entry.tarot.actor.toUpperCase();
  return (
    <article className="tarot-reveal" data-tone={tone}>
      <span className="tarot-reveal__stripe" aria-hidden="true" />
      <div className="tarot-reveal__glyph" aria-hidden="true">
        <Sparkles size={18} />
      </div>
      <div>
        <header className="tarot-reveal__head">
          <span className="tarot-reveal__deck">
            {entry.tarot.deck_name ?? "Tarot"}
          </span>
          <span className="tarot-reveal__card">{entry.tarot.card_name}</span>
          <span className="tarot-reveal__actor">{actorLabel}</span>
        </header>
        <p className="tarot-reveal__influence">{entry.tarot.influence}</p>
      </div>
    </article>
  );
}
