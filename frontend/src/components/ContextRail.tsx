import {
  BookOpen,
  ChevronRight,
  Compass,
  Drama,
  Gauge,
  Sparkles,
  Users,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import {
  usePlayerIds,
  useSessionStore,
} from "../store/sessionStore";
import type { CharacterRecord } from "../types";
import { shortText } from "../utils";
import { CharacterHud } from "./CharacterHud";
import { ClockBand } from "./ClockBand";
import { Modal } from "./Modal";
import { PinCard } from "./PinCard";
import { SheetRenderer } from "./SheetRenderer";

export function ContextRail() {
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

function stripFrontmatter(content: string): string {
  return content.replace(/^---\n[\s\S]*?\n---\n?/, "").replace(/^# .+\n?/, "").trim();
}

export type ContextRailFileOpener = (path: string) => void;
