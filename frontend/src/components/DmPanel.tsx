import {
  AlertTriangle,
  CircleDot,
  Clock3,
  Gauge,
  ListChecks,
  RefreshCcw,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { selectLatestDmTurn, useSessionStore } from "../store/sessionStore";
import type {
  ClockRecord,
  DmSurfaceBeat,
  EventRecord,
  GraphEntity,
  SceneTrackerRecord,
  TableFile,
  TarotRecord,
} from "../types";
import { classNames, formatTime, progressPercent, shortText } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";
import { Modal } from "./Modal";
import { SheetRenderer } from "./SheetRenderer";

interface PressureItem {
  id: string;
  kind: string;
  label: string;
  detail: string;
  value: number;
  max: number;
  status: string;
  visibility: string;
}

export function DmPanel() {
  const maraFilePath = "dm/persona.md";
  const runtime = useSessionStore((state) => state.runtime);
  const latestDmTurn = useSessionStore(selectLatestDmTurn);
  const databaseError = useSessionStore((state) => state.databaseError);
  const generatedAt = useSessionStore((state) => state.generatedAt);
  const isRefreshing = useSessionStore((state) => state.isPolling);
  const selectedFile = useSessionStore((state) => state.selectedFile);
  const isFileLoading = useSessionStore((state) => state.isFileLoading);
  const clocks = useSessionStore((state) => state.clocks);
  const sceneTrackers = useSessionStore((state) => state.sceneTrackers);
  const tarot = useSessionStore((state) => state.tarot);
  const events = useSessionStore((state) => state.events);
  const graph = useSessionStore((state) => state.graph);
  const dmSurface = useSessionStore((state) => state.dmSurface);
  const refreshCurrentState = useSessionStore(
    (state) => state.refreshCurrentState,
  );
  const loadFile = useSessionStore((state) => state.loadFile);
  const [isMaraOpen, setIsMaraOpen] = useState(false);
  const latestText =
    latestDmTurn?.markdown || latestDmTurn?.prose || runtime?.summary;
  const maraFile = selectedFile?.path === maraFilePath ? selectedFile : null;
  const pressureItems = useMemo(
    () => buildPressureItems(clocks, sceneTrackers),
    [clocks, sceneTrackers],
  );
  const dmTarot = useMemo(
    () => tarot.filter((item) => item.active && item.actor === "dm").slice(0, 1),
    [tarot],
  );
  const playEntities = useMemo(
    () => graph.entities.filter(isPlayRelevantEntity).slice(0, 6),
    [graph.entities],
  );
  const dmEvents = useMemo(
    () => events.filter(isPlayRelevantDmEvent).slice(-5).reverse(),
    [events],
  );
  const beats = dmSurface.beats.slice(-5).reverse();
  const dmFiles = dmSurface.files.slice(0, 2);
  const openMaraSheet = useCallback(() => {
    setIsMaraOpen(true);
    void loadFile(maraFilePath);
  }, [loadFile]);
  const closeMaraSheet = useCallback(() => setIsMaraOpen(false), []);

  return (
    <>
      <section className="dm-panel panel">
        <header className="panel-header">
          <div>
            <p className="eyebrow">Dungeon Master</p>
            <h1>
              <button
                className="heading-link"
                onClick={openMaraSheet}
                title="Open Mara's sheet"
                type="button"
              >
                Mara
              </button>
            </h1>
          </div>
          <div className="header-actions">
            <button
              aria-label="Open Mara's sheet"
              className="icon-button"
              onClick={openMaraSheet}
              type="button"
            >
              <UserRound aria-hidden="true" size={18} />
            </button>
            <span>{formatTime(generatedAt)}</span>
            <button
              aria-label="Refresh"
              className="icon-button"
              disabled={isRefreshing}
              onClick={() => void refreshCurrentState()}
              type="button"
            >
              <RefreshCcw aria-hidden="true" size={18} />
            </button>
          </div>
        </header>
        {databaseError && (
          <div className="status-banner">
            <AlertTriangle aria-hidden="true" size={17} />
            <span>{databaseError}</span>
          </div>
        )}
        <div className="dm-panel__body">
          <div className="dm-panel__summary">
            <div className="stat-strip">
              <span>Campaign: {runtime?.campaign ?? "unknown"}</span>
              <span>Status: {runtime?.status ?? "unknown"}</span>
              <span>Turn: {runtime?.turn_counter ?? 0}</span>
              <span>Mode: {runtime?.mode_stack?.at(-1) ?? "table"}</span>
              {dmSurface.current_scene && (
                <span>Scene: {dmSurface.current_scene.scene_id}</span>
              )}
            </div>
            <MarkdownBlock
              content={shortText(latestText, 760)}
              emptyLabel="No DM narrative"
              compact
            />
          </div>
          <div className="dm-panel__stack">
            <div className="mini-header">
              <span>Clocks & Trackers</span>
              <Clock3 aria-hidden="true" size={16} />
            </div>
            <div className="dm-state-list">
              {pressureItems.map((item) => (
                <PressureMeter item={item} key={item.id} />
              ))}
              {pressureItems.length === 0 && (
                <div className="empty-state">No active clocks or trackers</div>
              )}
            </div>
          </div>
          <DmCueStack
            beats={beats}
            dmEvents={dmEvents}
            dmFiles={dmFiles}
            dmTarot={dmTarot}
            playEntities={playEntities}
          />
        </div>
      </section>
      <Modal
        isOpen={isMaraOpen}
        onClose={closeMaraSheet}
        subtitle={maraFilePath}
        title={maraFile?.title ?? "Mara"}
      >
        <SheetRenderer file={maraFile} isLoading={isFileLoading} />
      </Modal>
    </>
  );
}

function DmCueStack({
  beats,
  dmEvents,
  dmFiles,
  dmTarot,
  playEntities,
}: {
  beats: DmSurfaceBeat[];
  dmEvents: EventRecord[];
  dmFiles: TableFile[];
  dmTarot: TarotRecord[];
  playEntities: GraphEntity[];
}) {
  return (
    <div className="dm-panel__stack">
      <div className="mini-header">
        <span>Beats & Cues</span>
        <ListChecks aria-hidden="true" size={16} />
      </div>
      <div className="dm-cue-list">
        {beats.map((beat) => (
          <article className="dm-cue" key={`${beat.source_path}-${beat.text}`}>
            <div className="dm-cue__label">
              <CircleDot aria-hidden="true" size={13} />
              <span>
                Beat
                {beat.scene_id ? ` / ${beat.scene_id}` : ""}
              </span>
            </div>
            <p title={beat.text}>{shortText(beat.text, 170)}</p>
          </article>
        ))}
        {dmFiles.map((file) => (
          <article className="dm-cue" key={file.path}>
            <div className="dm-cue__label">
              <Sparkles aria-hidden="true" size={13} />
              <span>{file.title || file.name || "Scene prep"}</span>
            </div>
            <p title={file.content}>
              {shortText(readableMarkdown(file.content), 170)}
            </p>
          </article>
        ))}
        {dmTarot.map((item) => (
          <article className="dm-cue" key={item.id}>
            <div className="dm-cue__label">
              <Sparkles aria-hidden="true" size={13} />
              <span>DM Tarot / {item.card_name}</span>
            </div>
            <p title={item.influence}>{shortText(item.influence, 170)}</p>
          </article>
        ))}
        {playEntities.map((entity) => (
          <article className="dm-cue" key={entity.uid ?? entity.id}>
            <div className="dm-cue__label">
              <Gauge aria-hidden="true" size={13} />
              <span>{entity.type ?? "cue"}</span>
            </div>
            <p title={entity.file_path ?? entity.title}>
              {entity.title}
              {entity.status ? ` — ${entity.status}` : ""}
            </p>
          </article>
        ))}
        {dmEvents.map((event) => (
          <article className="dm-cue" key={event.event_id}>
            <div className="dm-cue__label">
              <CircleDot aria-hidden="true" size={13} />
              <span>Event / turn {event.turn_id ?? "n/a"}</span>
            </div>
            <p title={event.summary}>{shortText(event.summary, 170)}</p>
          </article>
        ))}
        {beats.length === 0 &&
          dmFiles.length === 0 &&
          dmTarot.length === 0 &&
          playEntities.length === 0 &&
          dmEvents.length === 0 && (
            <div className="empty-state">No current DM cues</div>
          )}
      </div>
    </div>
  );
}

function PressureMeter({ item }: { item: PressureItem }) {
  const percent = progressPercent(item.value, item.max);
  const bucket = Math.ceil(percent / 5) * 5;
  return (
    <article className="pressure-meter">
      <div className="pressure-meter__head">
        <div>
          <strong>{item.label}</strong>
          <small>{item.detail}</small>
        </div>
        <span>
          {item.value}/{item.max}
        </span>
      </div>
      <div
        aria-label={`${item.label} ${item.value} of ${item.max}`}
        className={classNames("meter-bar", `meter-bar--p${bucket}`)}
        role="meter"
        aria-valuemax={item.max}
        aria-valuemin={0}
        aria-valuenow={item.value}
      >
        <span />
      </div>
      <div className="pressure-meter__meta">
        <span>{item.kind}</span>
        <span>{item.visibility}</span>
        <span>{item.status}</span>
      </div>
    </article>
  );
}

function buildPressureItems(
  clocks: ClockRecord[],
  sceneTrackers: SceneTrackerRecord[],
): PressureItem[] {
  const clockItems = clocks
    .filter((clock) => clock.status !== "archived")
    .map((clock) => ({
      id: `clock-${clock.clock_id}`,
      kind: `${clock.scope} clock`,
      label: clock.label || clock.clock_id,
      detail: clock.description || clock.anchor_id || clock.direction,
      value: clock.value,
      max: clock.max,
      status: clock.status,
      visibility: clock.visibility,
    }));
  const trackerItems = sceneTrackers
    .filter((tracker) => tracker.status !== "archived")
    .map((tracker) => ({
      id: `tracker-${tracker.tracker_id}`,
      kind: "scene tracker",
      label: tracker.label || tracker.tracker_id,
      detail: tracker.scene_id,
      value: tracker.value,
      max: tracker.max,
      status: tracker.status,
      visibility: tracker.visibility,
    }));
  return [...trackerItems, ...clockItems].slice(0, 8);
}

function isPlayRelevantEntity(entity: GraphEntity): boolean {
  const type = entity.type?.toLowerCase() ?? "";
  const status = entity.status?.toLowerCase() ?? "";
  if (!["hook", "scene-play", "secret", "hidden-knowledge"].includes(type)) {
    return false;
  }
  if (status && !["active", "live", "open", "draft-1"].includes(status)) {
    return false;
  }
  return true;
}

function isPlayRelevantDmEvent(event: { actor: string; summary: string }) {
  if (event.actor !== "dm") {
    return false;
  }
  const summary = event.summary.toLowerCase();
  return [
    "tracker ",
    "clock ",
    "initiative ",
    "mode ",
    "scene ",
    "handoff ",
    "beat:",
  ].some((term) => summary.includes(term));
}

function readableMarkdown(content: string): string {
  return content
    .replace(/^---\n[\s\S]*?\n---\n?/, "")
    .replace(/^# .+\n?/, "")
    .trim();
}
