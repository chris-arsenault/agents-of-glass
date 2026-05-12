import { RefreshCcw } from "lucide-react";
import { useMemo } from "react";

import { AGENT_DISPLAY, toneFor } from "../agentChroma";
import { selectLatestDmTurn, useSessionStore } from "../store/sessionStore";
import type { ClockRecord, SceneTrackerRecord } from "../types";
import { formatTime, progressPercent } from "../utils";
import { CampaignSelector } from "./CampaignSelector";

export function Scorebug({ onOpenCommand }: { onOpenCommand: () => void }) {
  const runtime = useSessionStore((state) => state.runtime);
  const generatedAt = useSessionStore((state) => state.generatedAt);
  const isPolling = useSessionStore((state) => state.isPolling);
  const refresh = useSessionStore((state) => state.refreshCurrentState);
  const turns = useSessionStore((state) => state.turns);
  const dmSurface = useSessionStore((state) => state.dmSurface);
  const clocks = useSessionStore((state) => state.clocks);
  const sceneTrackers = useSessionStore((state) => state.sceneTrackers);
  const latestDmTurn = useSessionStore(selectLatestDmTurn);

  const lastTurn = turns.at(-1);
  const composingTone = toneFor(runtime?.next_speakers?.[0]
    ? typeof runtime.next_speakers[0] === "string"
      ? runtime.next_speakers[0]
      : null
    : lastTurn?.speaker);
  const composingName = composingTone === "neutral"
    ? "idle"
    : AGENT_DISPLAY[composingTone];

  const scene = dmSurface.current_scene?.scene_id ??
    latestDmTurn?.scene_id ??
    lastTurn?.scene_id ??
    "—";
  const mode = coerceMode(
    runtime?.mode_stack?.at(-1) ?? lastTurn?.mode ?? "scene-play",
  );

  const highlightedClocks = useMemo(
    () => pickHighlightClocks(clocks, sceneTrackers),
    [clocks, sceneTrackers],
  );

  return (
    <div className="scorebug">
      <CampaignSelector />
      <div className="scorebug__turn">
        <span className="scorebug__turn-label">Turn</span>
        <span className="scorebug__turn-value">{runtime?.turn_counter ?? 0}</span>
      </div>
      <div className="scorebug__scene">
        <span className="scorebug__scene-mode">{mode}</span>
        <span className="scorebug__scene-id">{scene}</span>
      </div>
      <ComposingIndicator
        isLive={isPolling}
        name={composingName}
        tone={composingTone}
        runtimeStatus={runtime?.status}
      />
      <div className="scorebug__clocks">
        {highlightedClocks.map((band) => (
          <BandStrip key={band.id} {...band} />
        ))}
      </div>
      <span className="scorebug__time">{formatTime(generatedAt)}</span>
      <button
        aria-label="Refresh state"
        className="scorebug__refresh"
        disabled={isPolling}
        onClick={() => void refresh()}
        type="button"
      >
        <RefreshCcw aria-hidden="true" size={14} />
      </button>
      <button
        aria-label="Open command palette"
        className="scorebug__refresh"
        onClick={onOpenCommand}
        type="button"
        title="⌘K"
      >
        <span aria-hidden="true" style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>
          ⌘K
        </span>
      </button>
    </div>
  );
}

function ComposingIndicator({
  isLive,
  name,
  tone,
  runtimeStatus,
}: {
  isLive: boolean;
  name: string;
  tone: ReturnType<typeof toneFor>;
  runtimeStatus: string | undefined;
}) {
  return (
    <div
      className={`scorebug__composing${isLive ? " is-live" : ""}`}
      data-tone={tone}
    >
      <span className="scorebug__composing-dot" aria-hidden="true" />
      <span className="scorebug__composing-name">{name}</span>
      <span className="scorebug__composing-action">
        {isLive ? "polling…" : runtimeStatus ?? "idle"}
      </span>
    </div>
  );
}

interface ScoreBand {
  id: string;
  label: string;
  value: number;
  max: number;
  direction: "fills" | "drains";
  warn?: boolean;
}

function pickHighlightClocks(
  clocks: ClockRecord[],
  trackers: SceneTrackerRecord[],
): ScoreBand[] {
  const bands: ScoreBand[] = [];
  for (const t of trackers.slice(0, 2)) {
    if (t.status === "archived") continue;
    bands.push({
      id: `tracker-${t.tracker_id}`,
      label: t.label || t.tracker_id,
      value: t.value,
      max: t.max,
      direction: "fills",
      warn: progressPercent(t.value, t.max) > 65,
    });
  }
  for (const c of clocks.slice(0, 2)) {
    if (c.status === "archived") continue;
    bands.push({
      id: `clock-${c.clock_id}`,
      label: c.label || c.clock_id,
      value: c.value,
      max: c.max,
      direction: (c.direction as "fills" | "drains") ?? "fills",
      warn: progressPercent(c.value, c.max) > 65,
    });
  }
  return bands.slice(0, 3);
}

function coerceMode(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object") {
    const candidate = (value as Record<string, unknown>).mode
      ?? (value as Record<string, unknown>).name
      ?? (value as Record<string, unknown>).id;
    if (typeof candidate === "string") {
      return candidate;
    }
  }
  return "scene-play";
}

function BandStrip({ label, value, max, warn }: ScoreBand) {
  const filled = Math.max(0, Math.min(value, max));
  return (
    <span className="band-strip" title={`${label} ${value}/${max}`}>
      <span>{label}</span>
      <span className="band-strip__bars" aria-hidden="true">
        {Array.from({ length: max }).map((_, i) => (
          <span
            key={i}
            className={`band-strip__bar${i < filled ? " is-on" : ""}${warn ? " is-warn" : ""}`}
          />
        ))}
      </span>
      <span className="band-strip__count">
        {value}/{max}
      </span>
    </span>
  );
}
