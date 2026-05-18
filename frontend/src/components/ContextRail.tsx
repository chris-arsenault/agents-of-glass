import {
  BookOpen,
  ChevronRight,
  Compass,
  Drama,
  FileText,
  Gauge,
  ListTree,
  Sparkles,
  Users,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import {
  usePlayerIds,
  useSessionStore,
} from "../store/sessionStore";
import type {
  CharacterRecord,
  SceneIndexArc,
  SceneIndexScene,
} from "../types";
import { classNames, prettifyTitle, shortText } from "../utils";
import { CharacterHud } from "./CharacterHud";
import { ClockBand } from "./ClockBand";
import { Modal } from "./Modal";
import { PinCard } from "./PinCard";
import { SheetRenderer } from "./SheetRenderer";

interface ContextRailProps {
  onJumpTurn?: (turnId: number) => void;
}

export function ContextRail({ onJumpTurn }: ContextRailProps = {}) {
  const playerIds = usePlayerIds();
  const characters = useSessionStore((state) => state.characters);
  const clocks = useSessionStore((state) => state.clocks);
  const sceneTrackers = useSessionStore((state) => state.sceneTrackers);
  const dmSurface = useSessionStore((state) => state.dmSurface);
  const table = useSessionStore((state) => state.table);
  const tarot = useSessionStore((state) => state.tarot);
  const graph = useSessionStore((state) => state.graph);
  const loadFile = useSessionStore((state) => state.loadFile);
  const selectedFile = useSessionStore((state) => state.selectedFile);
  const isFileLoading = useSessionStore((state) => state.isFileLoading);
  const sceneIndex = useSessionStore((state) => state.sceneIndex);
  const sceneIndexActive = useSessionStore((state) => state.sceneIndexActive);
  const loadTurnsAround = useSessionStore((state) => state.loadTurnsAround);

  const [modalPath, setModalPath] = useState<string | null>(null);

  const open = useCallback(
    (path: string) => {
      setModalPath(path);
      void loadFile(path);
    },
    [loadFile],
  );
  const close = useCallback(() => setModalPath(null), []);

  const activeScene = dmSurface.current_scene;
  const scenePrep = useMemo(() => {
    return (
      table.scene ??
      dmSurface.files.find((f) => f.path?.endsWith("/prep.md")) ??
      null
    );
  }, [table.scene, dmSurface.files]);

  const beats = dmSurface.beats.slice(-3).reverse();
  const dmTarot = tarot.filter((t) => t.active && t.actor === "dm").slice(0, 1);
  const lorePins = useMemo(
    () =>
      graph.entities
        .filter((entity) => {
          const type = entity.type?.toLowerCase() ?? "";
          return ["hook", "scene-play", "secret", "hidden-knowledge"].includes(
            type,
          );
        })
        .slice(0, 4),
    [graph.entities],
  );

  const characterByPlayer = useMemo(() => {
    const map = new Map<string, CharacterRecord>();
    for (const c of characters) {
      map.set(c.player_id, c);
    }
    return map;
  }, [characters]);

  const openCharacterSheet = useCallback(
    (playerId: string) => {
      open(`players/${playerId}/public/character.md`);
    },
    [open],
  );

  const jumpToTurn = useCallback(
    (turnId: number) => {
      void loadTurnsAround(turnId);
      onJumpTurn?.(turnId);
    },
    [loadTurnsAround, onJumpTurn],
  );

  const totalScenes = useMemo(
    () => sceneIndex.reduce((sum, arc) => sum + arc.scenes.length, 0),
    [sceneIndex],
  );

  const modalSubtitle = modalPath ?? "";
  const modalTitle = selectedFile?.path === modalPath
    ? selectedFile.title || modalPath || "Document"
    : modalPath || "Document";

  return (
    <>
      <aside className="rail" aria-label="Context this turn">
        <header className="rail__head">
          <div className="rail__head-title">
            <span className="rail__eyebrow">Context this turn</span>
            <span className="rail__name">
              {activeScene?.scene_id ?? "—"}
            </span>
          </div>
        </header>
        <div className="rail__body">
          <Section
            count={totalScenes}
            defaultOpen
            icon={ListTree}
            label="Timeline"
          >
            <TimelineList
              activeArcId={sceneIndexActive?.arc_id ?? null}
              activeSceneId={sceneIndexActive?.scene_id ?? null}
              arcs={sceneIndex}
              onJumpTurn={jumpToTurn}
              onOpenSummary={open}
            />
          </Section>

          <Section count={scenePrep ? 1 : 0} icon={Sparkles} label="Scene Prep">
            {scenePrep ? (
              <PinCard
                excerpt={shortText(stripFrontmatter(scenePrep.content), 240)}
                kind="scene"
                onOpen={() => open(scenePrep.path)}
                sub={scenePrep.path}
                title={scenePrep.title || activeScene?.scene_id || "Scene"}
                icon={Drama}
              />
            ) : (
              <EmptyTag>No active scene</EmptyTag>
            )}
          </Section>

          <Section
            count={
              clocks.filter((c) => c.status !== "archived").length +
              sceneTrackers.filter((t) => t.status !== "archived").length
            }
            icon={Gauge}
            label="Clocks & Trackers"
          >
            {sceneTrackers
              .filter((t) => t.status !== "archived")
              .slice(0, 3)
              .map((t) => (
                <ClockBand
                  detail={t.scene_id}
                  key={`tracker-${t.tracker_id}`}
                  label={t.label || t.tracker_id}
                  max={t.max}
                  scope="scene tracker"
                  status={t.status}
                  value={t.value}
                  visibility={t.visibility}
                />
              ))}
            {clocks
              .filter((c) => c.status !== "archived")
              .slice(0, 4)
              .map((c) => (
                <ClockBand
                  detail={c.description || c.anchor_id || c.direction}
                  key={`clock-${c.clock_id}`}
                  label={c.label || c.clock_id}
                  max={c.max}
                  scope={c.scope}
                  status={c.status}
                  value={c.value}
                  visibility={c.visibility}
                />
              ))}
            {clocks.length + sceneTrackers.length === 0 && (
              <EmptyTag>No active clocks</EmptyTag>
            )}
          </Section>

          <Section
            count={beats.length + dmTarot.length}
            icon={BookOpen}
            label="Beats & Cues"
          >
            {beats.length === 0 && dmTarot.length === 0 && (
              <EmptyTag>No active beats</EmptyTag>
            )}
            {beats.map((beat) => (
              <PinCard
                excerpt={shortText(beat.text, 180)}
                kind="beat"
                key={`${beat.source_path}-${beat.text.slice(0, 20)}`}
                sub={beat.scene_id ?? beat.source_path}
                title={beat.scene_id ? `Beat · ${beat.scene_id}` : "Beat"}
                icon={Sparkles}
              />
            ))}
            {dmTarot.map((card) => (
              <PinCard
                excerpt={card.influence}
                kind="dm tarot"
                key={`tarot-${card.id}`}
                sub={card.deck_name}
                title={card.card_name}
                icon={Sparkles}
              />
            ))}
          </Section>

          {lorePins.length > 0 && (
            <Section count={lorePins.length} icon={Compass} label="Lore Pins">
              {lorePins.map((entity) => (
                <PinCard
                  kind={entity.type ?? "entity"}
                  key={entity.uid ?? entity.id ?? entity.title}
                  onOpen={
                    entity.file_path ? () => open(entity.file_path!) : undefined
                  }
                  sub={entity.file_path ?? entity.status}
                  title={entity.title ?? entity.type ?? "Entity"}
                  icon={BookOpen}
                />
              ))}
            </Section>
          )}

          <Section count={playerIds.length} icon={Users} label="Players">
            {playerIds.map((playerId) => (
              <CharacterHud
                key={playerId}
                onOpen={openCharacterSheet}
                playerId={playerId}
              />
            ))}
            {playerIds.length === 0 && <EmptyTag>No players</EmptyTag>}
          </Section>
        </div>
      </aside>
      <Modal
        isOpen={modalPath !== null}
        onClose={close}
        subtitle={modalSubtitle}
        title={modalTitle}
      >
        <SheetRenderer
          file={selectedFile?.path === modalPath ? selectedFile : null}
          isLoading={isFileLoading}
        />
      </Modal>
    </>
  );
}

function Section({
  children,
  count,
  defaultOpen = false,
  icon: Icon,
  label,
}: {
  children: React.ReactNode;
  count?: number;
  defaultOpen?: boolean;
  icon: typeof Sparkles;
  label: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={`rail__section${open ? " is-open" : ""}`}>
      <button
        aria-expanded={open}
        className="rail__section-head rail__section-toggle"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <ChevronRight
          aria-hidden="true"
          className="rail__section-caret"
          size={12}
        />
        <span>{label}</span>
        {count !== undefined && (
          <span className="rail__section-count">{count}</span>
        )}
        <span style={{ flex: 1 }} />
        <Icon aria-hidden="true" size={12} />
      </button>
      {open && <div className="rail__section-body">{children}</div>}
    </section>
  );
}

function EmptyTag({ children }: { children: React.ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

function TimelineList({
  activeArcId,
  activeSceneId,
  arcs,
  onJumpTurn,
  onOpenSummary,
}: {
  activeArcId: string | null;
  activeSceneId: string | null;
  arcs: SceneIndexArc[];
  onJumpTurn: (turnId: number) => void;
  onOpenSummary: (path: string) => void;
}) {
  if (arcs.length === 0) {
    return <EmptyTag>No turns yet</EmptyTag>;
  }
  return (
    <div className="timeline">
      {arcs.map((arc) => (
        <TimelineArc
          activeArcId={activeArcId}
          activeSceneId={activeSceneId}
          arc={arc}
          key={`arc-${arc.arc_id ?? "unscoped"}`}
          onJumpTurn={onJumpTurn}
          onOpenSummary={onOpenSummary}
        />
      ))}
    </div>
  );
}

function TimelineArc({
  activeArcId,
  activeSceneId,
  arc,
  onJumpTurn,
  onOpenSummary,
}: {
  activeArcId: string | null;
  activeSceneId: string | null;
  arc: SceneIndexArc;
  onJumpTurn: (turnId: number) => void;
  onOpenSummary: (path: string) => void;
}) {
  const isActiveArc = arc.arc_id !== null && arc.arc_id === activeArcId;
  const arcTitle = arc.arc_id ? prettifyTitle(arc.arc_id) : "Unscoped";
  return (
    <div className={classNames("timeline__arc", isActiveArc && "is-active")}>
      <div className="timeline__arc-head">
        <button
          className="timeline__arc-title"
          onClick={() => onJumpTurn(arc.first_turn_id)}
          title={`Jump to turn ${arc.first_turn_id}`}
          type="button"
        >
          {arcTitle}
        </button>
        <span className="timeline__range">
          {arc.first_turn_id}–{arc.last_turn_id}
        </span>
        {arc.summary_path && (
          <button
            aria-label={`Open ${arcTitle} summary`}
            className="timeline__doc"
            onClick={() => onOpenSummary(arc.summary_path!)}
            title="Open arc summary"
            type="button"
          >
            <FileText aria-hidden="true" size={11} />
          </button>
        )}
      </div>
      <ul className="timeline__scenes">
        {arc.scenes.map((scene) => (
          <TimelineScene
            isActive={
              scene.scene_id !== null &&
              scene.scene_id === activeSceneId &&
              arc.arc_id === activeArcId
            }
            key={`scene-${arc.arc_id ?? "unscoped"}-${scene.scene_id ?? "none"}`}
            onJumpTurn={onJumpTurn}
            onOpenSummary={onOpenSummary}
            scene={scene}
          />
        ))}
      </ul>
    </div>
  );
}

function TimelineScene({
  isActive,
  onJumpTurn,
  onOpenSummary,
  scene,
}: {
  isActive: boolean;
  onJumpTurn: (turnId: number) => void;
  onOpenSummary: (path: string) => void;
  scene: SceneIndexScene;
}) {
  const title = sceneLabel(scene);
  const status = scene.status?.toLowerCase() ?? "";
  return (
    <li
      className={classNames(
        "timeline__scene",
        isActive && "is-active",
        status && `is-status-${status}`,
      )}
    >
      <button
        className="timeline__scene-title"
        onClick={() => onJumpTurn(scene.first_turn_id)}
        title={`Jump to turn ${scene.first_turn_id}`}
        type="button"
      >
        <span className="timeline__scene-name">{title}</span>
        <span className="timeline__scene-meta">
          {scene.scene_type ?? scene.mode ?? "—"}
          {scene.status ? ` · ${scene.status}` : ""}
        </span>
      </button>
      <span className="timeline__range">
        {scene.first_turn_id}–{scene.last_turn_id}
      </span>
      {scene.summary_path && (
        <button
          aria-label={`Open ${title} summary`}
          className="timeline__doc"
          onClick={() => onOpenSummary(scene.summary_path!)}
          title="Open scene summary"
          type="button"
        >
          <FileText aria-hidden="true" size={11} />
        </button>
      )}
    </li>
  );
}

function sceneLabel(scene: SceneIndexScene): string {
  if (scene.scene_id) {
    return prettifyTitle(scene.scene_id);
  }
  if (scene.mode) {
    return prettifyTitle(scene.mode);
  }
  return "Unscoped";
}

function stripFrontmatter(content: string): string {
  return content.replace(/^---\n[\s\S]*?\n---\n?/, "").replace(/^# .+\n?/, "").trim();
}

export type ContextRailFileOpener = (path: string) => void;
