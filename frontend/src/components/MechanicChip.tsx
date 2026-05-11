import {
  Activity,
  ArrowUpRight,
  Compass,
  Dice5,
  HeartPulse,
  Layers,
  Sparkle,
  Waves,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { MechanicEvent } from "../transcriptModel";

const KIND_ICON: Record<MechanicEvent["kind"], LucideIcon> = {
  roll: Dice5,
  pressure: Waves,
  hp: HeartPulse,
  momentum: ArrowUpRight,
  beat: Sparkle,
  mode: Compass,
  other: Layers,
};

export function MechanicChip({
  event,
  fresh,
}: {
  event: MechanicEvent;
  fresh?: boolean;
}) {
  const Icon = KIND_ICON[event.kind] ?? Activity;
  const outcome = (event.outcome || "").toLowerCase();

  return (
    <article
      className={`mechanic-chip${fresh ? " is-fresh" : ""}`}
      data-kind={event.kind}
    >
      <span className="mechanic-chip__glyph" aria-hidden="true">
        <Icon size={14} />
      </span>
      <span className="mechanic-chip__label">{event.label}</span>
      <span className="mechanic-chip__detail">
        {event.details.map((pair) => (
          <span className="mechanic-chip__detail-pair" key={`${pair.key}-${pair.value}`}>
            <span className="mechanic-chip__detail-key">{pair.key}</span>
            <span className="mechanic-chip__detail-val">{pair.value}</span>
          </span>
        ))}
        {event.kind === "roll" && typeof event.total === "number" &&
          typeof event.target === "number" && (
            <MarginBar total={event.total} target={event.target} />
          )}
      </span>
      {outcome && (
        <span className="mechanic-chip__outcome" data-outcome={outcome}>
          {outcome}
        </span>
      )}
    </article>
  );
}

function MarginBar({ total, target }: { total: number; target: number }) {
  // Visualise total vs target on a small bar — total is the value, target the
  // threshold. Useful telemetry that the prose line alone obscures.
  const ceiling = Math.max(total, target, 20);
  const totalPct = Math.min(100, Math.round((total / ceiling) * 100));
  const targetPct = Math.min(100, Math.round((target / ceiling) * 100));
  return (
    <span className="mechanic-chip__bar" aria-hidden="true">
      <span className="mechanic-chip__bar-track">
        <span
          className="mechanic-chip__bar-fill"
          style={{ width: `${totalPct}%` }}
        />
        <span
          style={{
            position: "absolute",
            left: `${targetPct}%`,
            top: -1,
            bottom: -1,
            width: 1,
            background: "var(--ink-muted)",
          }}
        />
      </span>
      <span className="mechanic-chip__detail-val">
        {total}/{target}
      </span>
    </span>
  );
}
