import type {
  EventRecord,
  MessageRecord,
  RollRecord,
  TarotRecord,
  TurnRecord,
} from "./types";

/**
 * Unified transcript stream — turns, tarot reveals, and stand-alone events
 * (mode transitions especially) merged + sorted by timestamp so the canvas
 * can render them as one append-only flow.
 */

export interface TranscriptTurnEntry {
  kind: "turn";
  id: string;
  timestamp: number;
  turn: TurnRecord;
  prose: ProseBlock[];
  mechanics: MechanicEvent[];
}

export interface TranscriptModeEntry {
  kind: "mode";
  id: string;
  timestamp: number;
  direction: "start" | "end";
  mode: string;
  sceneId: string | null;
  actor: string;
  summary: string;
}

export interface TranscriptTarotEntry {
  kind: "tarot";
  id: string;
  timestamp: number;
  tarot: TarotRecord;
}

export interface TranscriptFailEntry {
  kind: "fail";
  id: string;
  timestamp: number;
  message: string;
}

export interface TranscriptMessageEntry {
  kind: "message";
  id: string;
  timestamp: number;
  message: MessageRecord;
}

export type TranscriptEntry =
  | TranscriptTurnEntry
  | TranscriptModeEntry
  | TranscriptTarotEntry
  | TranscriptFailEntry;

export type TranscriptTimelineEntry =
  | TranscriptEntry
  | TranscriptMessageEntry;

export interface ProseBlock {
  kind: "ic" | "ooc";
  speaker: string | null;
  body: string;
}

export interface MechanicEvent {
  kind: "roll" | "pressure" | "hp" | "momentum" | "beat" | "mode" | "other";
  raw: string;
  label: string;
  details: Array<{ key: string; value: string }>;
  outcome?: string;
  rollRef?: RollRecord;
  total?: number;
  target?: number;
  margin?: number;
}

const OOC_PREFIX = /^(?<speaker>[A-Z][\w'-]+)\s*\(OOC\):/;

/** Parse a turn's prose into IC + OOC blocks. */
export function parseProse(prose: string): ProseBlock[] {
  const blocks: ProseBlock[] = [];
  if (!prose) {
    return blocks;
  }
  let buffer: ProseBlock | null = null;
  const flush = () => {
    if (buffer && buffer.body.trim()) {
      buffer.body = buffer.body.replace(/\s+$/, "");
      blocks.push(buffer);
    }
    buffer = null;
  };

  for (const rawLine of prose.split(/\r?\n/)) {
    const line = rawLine;
    // Skip mechanical event lines — they're extracted separately.
    if (/^>\s+/.test(line.trim())) {
      flush();
      continue;
    }
    const oocMatch = line.match(OOC_PREFIX);
    if (oocMatch) {
      flush();
      buffer = {
        kind: "ooc",
        speaker: oocMatch.groups?.speaker ?? null,
        body: line.replace(OOC_PREFIX, "").trim() + "\n",
      };
      continue;
    }
    if (!buffer) {
      buffer = { kind: "ic", speaker: null, body: "" };
    }
    buffer.body += line + "\n";
  }
  flush();

  // Collapse blocks down — clean trailing/leading whitespace.
  return blocks
    .map((block) => ({ ...block, body: block.body.trim() }))
    .filter((block) => block.body.length > 0);
}

/** Extract mechanical event lines from prose: lines starting with "> ". */
export function parseMechanicsFromProse(prose: string): MechanicEvent[] {
  if (!prose) {
    return [];
  }
  const events: MechanicEvent[] = [];
  for (const rawLine of prose.split(/\r?\n/)) {
    const trimmed = rawLine.trim();
    if (!trimmed.startsWith("> ")) {
      continue;
    }
    const body = trimmed.slice(2).trim();
    if (!body) continue;
    events.push(parseMechanicLine(body));
  }
  return events;
}

/** Parse a single inline mechanical event line. */
export function parseMechanicLine(raw: string): MechanicEvent {
  const stripped = raw
    .replace(/^[🎲❤⛓✨⚙↳·>]+\s*/u, "")
    .replace(/^[A-Za-z_]+\s*:\s*/, (match) => match)
    .trim();

  // Roll: "🎲 athletics (vitality) @ risky → 8 vs 9 → stall"
  if (
    /^(roll|🎲)/i.test(raw) ||
    /^\w+\s*\([\w\s]+\)\s*@/.test(stripped) ||
    /\d+\s*vs\s*\d+/.test(stripped)
  ) {
    return parseRollLine(stripped, raw);
  }
  // Pressure: "pressure Patrol leader HP: advance, impact d8=5 -> 2, -2 (8/8 -> 6/8)"
  if (/^pressure\b/i.test(stripped)) {
    return parsePressureLine(stripped, raw);
  }
  // HP: "❤ karrith hp -3 (5 → 2)" or "karrith HP: -3"
  if (/\bhp\b/i.test(stripped) && /[-+]?\d/.test(stripped)) {
    return parseHpLine(stripped, raw);
  }
  // Beat: "beat: ..."
  if (/^beat\s*:/i.test(stripped)) {
    return {
      kind: "beat",
      raw,
      label: "Beat",
      details: [
        { key: "text", value: stripped.replace(/^beat\s*:\s*/i, "") },
      ],
    };
  }
  // Mode: "mode start combat" or "Entering combat..."
  if (/^mode\b/i.test(stripped) || /^enter(ing)?\b/i.test(stripped)) {
    return {
      kind: "mode",
      raw,
      label: "Mode",
      details: [{ key: "event", value: stripped }],
    };
  }
  return {
    kind: "other",
    raw,
    label: "Event",
    details: [{ key: "line", value: stripped }],
  };
}

function parseRollLine(stripped: string, raw: string): MechanicEvent {
  const details: Array<{ key: string; value: string }> = [];
  let outcome: string | undefined;
  let total: number | undefined;
  let target: number | undefined;
  let margin: number | undefined;

  // skill (attribute) @ risk
  const skillMatch = stripped.match(
    /^(?<skill>[\w-]+)\s*(?:\((?<attr>[^)]+)\))?\s*(?:@\s*(?<risk>[\w-]+))?/,
  );
  if (skillMatch?.groups) {
    if (skillMatch.groups.skill) {
      details.push({ key: "skill", value: skillMatch.groups.skill });
    }
    if (skillMatch.groups.attr) {
      details.push({ key: "attr", value: skillMatch.groups.attr });
    }
    if (skillMatch.groups.risk) {
      details.push({ key: "risk", value: skillMatch.groups.risk });
    }
  }

  const totalMatch = stripped.match(/(\d+)\s*vs\s*(\d+)/);
  if (totalMatch) {
    total = Number(totalMatch[1]);
    target = Number(totalMatch[2]);
    margin = total - target;
    details.push({ key: "result", value: `${total} vs ${target}` });
    details.push({
      key: "margin",
      value: (margin > 0 ? "+" : "") + margin,
    });
  }
  const outcomeMatch = stripped.match(/→\s*([\w-]+)\s*$/) ||
    stripped.match(/->\s*([\w-]+)\s*$/);
  if (outcomeMatch) {
    outcome = outcomeMatch[1].toLowerCase();
  }
  return {
    kind: "roll",
    raw,
    label: "Roll",
    details,
    outcome,
    total,
    target,
    margin,
  };
}

function parsePressureLine(stripped: string, raw: string): MechanicEvent {
  const details: Array<{ key: string; value: string }> = [];
  const targetMatch = stripped.match(/^pressure\s+(?<target>[^:]+):/i);
  if (targetMatch?.groups?.target) {
    details.push({ key: "target", value: targetMatch.groups.target.trim() });
  }
  const directionMatch = stripped.match(/\b(advance|retreat|fill|deplete)\b/i);
  if (directionMatch) {
    details.push({ key: "dir", value: directionMatch[1].toLowerCase() });
  }
  const impactMatch = stripped.match(/impact\s+([^,]+?)(?:\s*,|\s*$)/i);
  if (impactMatch) {
    details.push({ key: "impact", value: impactMatch[1].trim() });
  }
  const deltaMatch = stripped.match(/[-+]\d+\s*\(([^)]+)\)/);
  if (deltaMatch) {
    details.push({ key: "track", value: deltaMatch[1] });
  } else {
    const trackOnly = stripped.match(/\(([0-9/]+\s*(?:→|->)\s*[0-9/]+)\)/);
    if (trackOnly) {
      details.push({ key: "track", value: trackOnly[1] });
    }
  }
  const outcome = directionMatch?.[1].toLowerCase() === "advance"
    ? "success"
    : undefined;
  return {
    kind: "pressure",
    raw,
    label: "Pressure",
    details,
    outcome,
  };
}

function parseHpLine(stripped: string, raw: string): MechanicEvent {
  const details: Array<{ key: string; value: string }> = [];
  const actorMatch = stripped.match(/^([\w-]+)\s+HP/i);
  if (actorMatch) {
    details.push({ key: "actor", value: actorMatch[1] });
  }
  const deltaMatch = stripped.match(/([-+]\d+)/);
  if (deltaMatch) {
    details.push({ key: "delta", value: deltaMatch[1] });
  }
  const trackMatch = stripped.match(/\(([0-9/]+\s*(?:→|->)\s*[0-9/]+)\)/);
  if (trackMatch) {
    details.push({ key: "after", value: trackMatch[1] });
  }
  return {
    kind: "hp",
    raw,
    label: "HP",
    details,
  };
}

interface BuildStreamArgs {
  turns: TurnRecord[];
  events: EventRecord[];
  tarot: TarotRecord[];
  rolls: RollRecord[];
  filter?: TranscriptFilter;
}

export type TranscriptFilter = "all" | "narrative" | "mechanics";

interface BuildInterleavedStreamArgs extends BuildStreamArgs {
  messages: MessageRecord[];
}

export function buildTranscriptStream({
  turns,
  events,
  tarot,
  rolls,
  filter = "all",
}: BuildStreamArgs): TranscriptEntry[] {
  const entries: TranscriptEntry[] = [];

  for (const turn of turns) {
    const ts = parseTimestamp(turn.created_at || turn.ts);
    const text = turn.markdown || turn.prose || "";
    const prose = parseProse(text);
    const mechanics = enrichMechanics(parseMechanicsFromProse(text), rolls);
    if (
      filter === "narrative" && prose.length === 0 && mechanics.length === 0
    ) {
      continue;
    }
    if (filter === "mechanics" && mechanics.length === 0) {
      continue;
    }
    entries.push({
      kind: "turn",
      id: `turn-${turn.turn_id}`,
      timestamp: ts,
      turn,
      prose,
      mechanics,
    });
  }

  if (filter !== "mechanics") {
    for (const card of tarot) {
      if (!card.active) continue;
      entries.push({
        kind: "tarot",
        id: `tarot-${card.id}`,
        timestamp: cardTimestamp(card),
        tarot: card,
      });
    }
  }

  // Stand-alone mode transitions surfaced from event log if not already inlined.
  if (filter !== "narrative") {
    for (const event of events) {
      const summary = (event.summary ?? "").toLowerCase();
      if (event.event_type === "mode" || /^mode\s+(start|end)/.test(summary)) {
        const direction = summary.includes("end") ? "end" : "start";
        const modeMatch = summary.match(/mode\s+(?:start|end)\s+(\S+)/);
        entries.push({
          kind: "mode",
          id: `mode-${event.event_id}`,
          timestamp: parseTimestamp(event.created_at),
          direction,
          mode: modeMatch?.[1] ?? "—",
          sceneId: event.scene_id,
          actor: event.actor,
          summary: event.summary,
        });
      }
    }
  }

  entries.sort(compareTimelineEntries);

  return entries;
}

export function buildMessageStream(
  messages: MessageRecord[],
): TranscriptMessageEntry[] {
  const entries = messages.map((message) => ({
    kind: "message" as const,
    id: `message-${message.id}`,
    timestamp: parseTimestamp(message.created_at),
    message,
  }));
  entries.sort(compareTimelineEntries);
  return entries;
}

export function buildInterleavedStream({
  turns,
  events,
  tarot,
  rolls,
  messages,
  filter = "all",
}: BuildInterleavedStreamArgs): TranscriptTimelineEntry[] {
  const entries: TranscriptTimelineEntry[] = [
    ...buildTranscriptStream({ turns, events, tarot, rolls, filter }),
    ...buildMessageStream(messages),
  ];
  entries.sort(compareTimelineEntries);
  return entries;
}

function enrichMechanics(
  events: MechanicEvent[],
  rolls: RollRecord[],
): MechanicEvent[] {
  if (events.length === 0 || rolls.length === 0) {
    return events;
  }
  // For each roll event, try to match with the most recent un-claimed roll.
  let cursor = 0;
  return events.map((event) => {
    if (event.kind !== "roll") {
      return event;
    }
    const skill = event.details.find((d) => d.key === "skill")?.value;
    while (cursor < rolls.length) {
      const roll = rolls[cursor];
      cursor += 1;
      if (!skill || roll.skill?.toLowerCase() === skill.toLowerCase()) {
        return {
          ...event,
          rollRef: roll,
          outcome: event.outcome ?? roll.outcome,
          total: event.total ?? roll.total,
          target: event.target ?? roll.target,
          margin: event.margin ?? roll.margin,
        };
      }
    }
    return event;
  });
}

function compareTimelineEntries(
  a: { timestamp: number; id: string },
  b: { timestamp: number; id: string },
): number {
  if (a.timestamp === b.timestamp) {
    return a.id.localeCompare(b.id);
  }
  return a.timestamp - b.timestamp;
}

function parseTimestamp(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function cardTimestamp(card: TarotRecord): number {
  // tarot cards don't carry a timestamp; approximate by their starts_turn.
  return (card.starts_turn ?? 0) * 1000;
}
