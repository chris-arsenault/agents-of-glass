import { Compass, Swords, Footprints, MessagesSquare, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { TranscriptModeEntry } from "../transcriptModel";

const MODE_ICON: Record<string, LucideIcon> = {
  combat: Swords,
  chase: Footprints,
  "social-pressure": MessagesSquare,
  social: MessagesSquare,
  "scene-play": Sparkles,
  prelude: Sparkles,
};

export function ModeMarquee({ entry }: { entry: TranscriptModeEntry }) {
  const Icon = MODE_ICON[entry.mode.toLowerCase()] ?? Compass;
  const word = entry.direction === "end" ? "Closing" : "Entering";
  return (
    <div className="mode-marquee" role="separator" aria-label={`${word} ${entry.mode}`}>
      <div className="mode-marquee__rule" aria-hidden="true" />
      <div className="mode-marquee__caption">
        <Icon aria-hidden="true" size={14} />
        <span>{word}</span>
        <strong>{entry.mode}</strong>
        {entry.sceneId && <span>· {entry.sceneId}</span>}
      </div>
      <div className="mode-marquee__rule" aria-hidden="true" />
    </div>
  );
}
