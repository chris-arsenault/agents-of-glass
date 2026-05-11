import {
  Activity,
  BookOpen,
  Dice5,
  FileText,
  LucideIcon,
  ScrollText,
} from "lucide-react";
import { useMemo, useState } from "react";

import { useSessionStore } from "../store/sessionStore";
import type { RollRecord, TableFile } from "../types";
import { formatTime, shortText } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";

interface TableCard {
  id: string;
  kind: string;
  title: string;
  subtitle: string;
  body: string;
  meta: string[];
  path?: string;
  Icon: LucideIcon;
}

export function TablePanels() {
  const table = useSessionStore((state) => state.table);
  const turns = useSessionStore((state) => state.turns);
  const rolls = useSessionStore((state) => state.rolls);
  const loadFile = useSessionStore((state) => state.loadFile);
  const latestTurn = turns.at(-1);
  const latestRoll = rolls.at(-1);
  const tableCards = useMemo(
    () =>
      buildTableCards({
        tableFiles: table.files,
        tableIndex: table.index,
        tableScene: table.scene,
      }),
    [table.files, table.index, table.scene],
  );
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const selectedCard =
    tableCards.find((card) => card.id === selectedCardId) ?? tableCards[0];

  function selectCard(card: TableCard) {
    setSelectedCardId(card.id);
    if (card.path) {
      void loadFile(card.path);
    }
  }

  return (
    <section className="table-row">
      <div className="table-view panel">
        <header className="panel-header panel-header--compact">
          <div>
            <p className="eyebrow">Active Table</p>
            <h2>{table.scene?.title ?? latestTurn?.scene_id ?? "Current Scene"}</h2>
          </div>
          <div className="table-header-actions">
            {latestRoll && <LatestRollLane roll={latestRoll} />}
            <ScrollText aria-hidden="true" size={19} />
          </div>
        </header>
        <div className="table-card-grid">
          {tableCards.map((card) => {
            const Icon = card.Icon;
            return (
              <button
                className={`table-card ${selectedCard?.id === card.id ? "is-active" : ""}`}
                key={card.id}
                onClick={() => selectCard(card)}
                type="button"
              >
                <div className="table-card__head">
                  <Icon aria-hidden="true" size={17} />
                  <span>{card.kind}</span>
                </div>
                <strong>{card.title}</strong>
                <small>{card.subtitle}</small>
                {card.meta.length > 0 && (
                  <div className="table-card__meta">
                    {card.meta.slice(0, 3).map((item) => (
                      <span key={item}>{item}</span>
                    ))}
                  </div>
                )}
              </button>
            );
          })}
          {tableCards.length === 0 && (
            <div className="empty-state">No active table content</div>
          )}
        </div>
      </div>
      <div className="turn-summary panel">
        <header className="panel-header panel-header--compact">
          <div>
            <p className="eyebrow">Table Detail</p>
            <h2>{selectedCard?.title ?? latestTurn?.speaker ?? "No selection"}</h2>
          </div>
          <Activity aria-hidden="true" size={19} />
        </header>
        <MarkdownBlock
          content={selectedCard?.body}
          emptyLabel="Select a table card"
          compact
        />
        <div className="table-context">
          <FileText aria-hidden="true" size={16} />
          <span>{tableCards.length} table cards</span>
          <span>{table.files.length} table files</span>
          {selectedCard?.path && <span>{selectedCard.path}</span>}
        </div>
      </div>
    </section>
  );
}

function LatestRollLane({ roll }: { roll: RollRecord }) {
  const chips = rollMetadataChips(roll);
  const title = JSON.stringify(roll, null, 2);
  return (
    <div className="latest-roll-lane" title={title}>
      <Dice5 aria-hidden="true" size={16} />
      <div className="latest-roll-lane__body">
        <span className="latest-roll-lane__label">Latest roll</span>
        <strong>
          {roll.actor}: {roll.skill} + {roll.attribute}
        </strong>
        <div className="latest-roll-meta">
          {chips.map((chip) => (
            <span key={chip.label}>
              <b>{chip.label}</b>
              {chip.value}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function rollMetadataChips(
  roll: RollRecord,
): Array<{ label: string; value: string }> {
  const dice = roll.dice.join(" + ");
  const known: Array<[string, unknown]> = [
    ["dice", dice],
    ["total", roll.total],
    ["target", roll.target],
    ["margin", signedNumber(roll.margin)],
    ["outcome", roll.outcome],
    ["risk", roll.risk],
    ["character", roll.character_id],
    ["scene", roll.scene_id],
    ["target id", roll.target_id],
    ["skill tier", roll.skill_tier],
    ["skill mod", signedNumber(roll.skill_modifier)],
    ["attribute tier", roll.attribute_tier],
    ["attribute mod", signedNumber(roll.attribute_modifier)],
    ["momentum", momentumLabel(roll)],
    ["time", formatTime(roll.created_at)],
    ["roll id", roll.roll_id],
    ["session", roll.session_id],
    ["campaign", roll.campaign_id],
  ];
  const nested: Array<[string, unknown]> = Object.entries(
    roll.metadata ?? {},
  ).map(([key, value]) => [`meta.${key}`, value]);
  return [...known, ...nested]
    .map(([label, value]) => ({ label, value: formatRollValue(value) }))
    .filter((chip) => chip.value !== "");
}

function signedNumber(value: number | undefined): string {
  if (value === undefined) {
    return "";
  }
  return value > 0 ? `+${value}` : String(value);
}

function momentumLabel(roll: RollRecord): string {
  if (roll.momentum_in === undefined && roll.momentum_out === undefined) {
    return "";
  }
  const delta = signedNumber(roll.momentum_delta);
  const suffix = delta ? ` (${delta})` : "";
  return `${roll.momentum_in ?? "?"} -> ${roll.momentum_out ?? "?"}${suffix}`;
}

function formatRollValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map(formatRollValue).filter(Boolean).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function buildTableCards({
  tableFiles,
  tableIndex,
  tableScene,
}: {
  tableFiles: TableFile[];
  tableIndex: TableFile | null;
  tableScene: TableFile | null;
}): TableCard[] {
  const cards: TableCard[] = [];
  if (tableScene) {
    const status = frontmatterValue(tableScene.content, "status") ?? "active";
    cards.push({
      id: "table-scene",
      kind: "Scene",
      title: tableScene.title || "Scene",
      subtitle: status === "inactive" ? "No scene is currently active" : "Current scene state",
      body: readableMarkdown(tableScene.content),
      meta: [status],
      path: tablePath(tableScene),
      Icon: ScrollText,
    });
  }
  if (tableIndex) {
    cards.push({
      id: "table-index",
      kind: "Table",
      title: tableIndex.title || "Table index",
      subtitle: "Visible table continuity",
      body: readableMarkdown(tableIndex.content),
      meta: [],
      path: tablePath(tableIndex),
      Icon: BookOpen,
    });
  }
  for (const file of tableFiles.slice(0, 8)) {
    cards.push({
      id: `file-${file.path}`,
      kind: "File",
      title: file.title || file.name || file.path,
      subtitle: file.path,
      body:
        readableMarkdown(file.content) ||
        `Open \`${file.path}\` for the table handout or reference file.`,
      meta: [],
      path: file.path,
      Icon: FileText,
    });
  }
  return cards;
}

function tablePath(file: TableFile): string {
  return file.path.includes("/") ? file.path : `table/${file.path}`;
}

function frontmatterValue(content: string, key: string): string | undefined {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) {
    return undefined;
  }
  const line = match[1]
    .split("\n")
    .find((item) => item.toLowerCase().startsWith(`${key.toLowerCase()}:`));
  return line?.split(":").slice(1).join(":").trim() || undefined;
}

function readableMarkdown(content: string): string {
  return shortText(
    content
      .replace(/^---\n[\s\S]*?\n---\n?/, "")
      .replace(/^# .+\n?/, "")
      .trim(),
    900,
  );
}
