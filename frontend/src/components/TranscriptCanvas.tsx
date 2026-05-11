import { AlertTriangle, Bookmark, Filter, ScrollText } from "lucide-react";
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useSessionStore } from "../store/sessionStore";
import {
  buildTranscriptStream,
  type TranscriptEntry,
  type TranscriptFilter,
} from "../transcriptModel";
import { MessageCard } from "./MessageCard";
import { ModeMarquee } from "./ModeMarquee";
import { TarotReveal } from "./TarotReveal";
import { TurnCard } from "./TurnCard";

type StageView = "transcript" | "bus";

interface CanvasProps {
  jumpTurnId: number | null;
  onJumpHandled: () => void;
}

export function TranscriptCanvas({ jumpTurnId, onJumpHandled }: CanvasProps) {
  const turns = useSessionStore((state) => state.turns);
  const events = useSessionStore((state) => state.events);
  const tarot = useSessionStore((state) => state.tarot);
  const rolls = useSessionStore((state) => state.rolls);
  const messages = useSessionStore((state) => state.messages);
  const characters = useSessionStore((state) => state.characters);

  const [view, setView] = useState<StageView>("transcript");
  const [filter, setFilter] = useState<TranscriptFilter>("all");

  const stream = useMemo(
    () => buildTranscriptStream({ turns, events, tarot, rolls, filter }),
    [turns, events, tarot, rolls, filter],
  );

  const characterByPlayer = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of characters) {
      map.set(c.player_id, c.name);
      map.set(c.character_id, c.name);
    }
    return map;
  }, [characters]);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const lastEntryIdRef = useRef<string | null>(null);
  const freshEntryIdRef = useRef<string | null>(null);

  // Autoscroll on new entries.
  useLayoutEffect(() => {
    const last = stream.at(-1);
    if (!last) {
      return;
    }
    if (lastEntryIdRef.current !== last.id) {
      freshEntryIdRef.current = last.id;
      lastEntryIdRef.current = last.id;
      const node = scrollRef.current;
      if (node) {
        node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
      }
    }
  }, [stream]);

  // Jump-to-turn (from agent lane click or cmd-k).
  useEffect(() => {
    if (jumpTurnId === null) return;
    const node = scrollRef.current;
    if (!node) return;
    const target = node.querySelector(`[data-turn-id="${jumpTurnId}"]`);
    if (target instanceof HTMLElement) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("is-fresh");
      window.setTimeout(() => target.classList.remove("is-fresh"), 1600);
    }
    onJumpHandled();
  }, [jumpTurnId, onJumpHandled]);

  return (
    <section className="stage" aria-label="Transcript">
      <header className="stage__head">
        <div className="stage__head-title">
          <span className="stage__head-eyebrow">
            {view === "transcript" ? "Conclave transcript" : "Message bus"}
          </span>
          <span className="stage__head-name">
            {view === "transcript" ? "Live ledger" : "Inter-agent comms"}
          </span>
        </div>
        <div className="stage__head-controls" role="tablist">
          <ViewToggle view={view} setView={setView} />
          {view === "transcript" && (
            <FilterToggle filter={filter} setFilter={setFilter} />
          )}
        </div>
      </header>
      <div className="stage__transcript" ref={scrollRef}>
        {view === "transcript" ? (
          stream.length === 0 ? (
            <div className="empty-state">No transcript entries yet.</div>
          ) : (
            stream.map((entry) =>
              renderEntry(
                entry,
                characterByPlayer,
                freshEntryIdRef.current === entry.id,
              ),
            )
          )
        ) : messages.length === 0 ? (
          <div className="empty-state">No bus traffic.</div>
        ) : (
          messages.map((message) => (
            <MessageCard key={message.id} message={message} />
          ))
        )}
      </div>
    </section>
  );
}

function renderEntry(
  entry: TranscriptEntry,
  characterByPlayer: Map<string, string>,
  fresh: boolean,
) {
  if (entry.kind === "turn") {
    const character =
      characterByPlayer.get(entry.turn.speaker) ??
      (entry.turn.character_id
        ? characterByPlayer.get(entry.turn.character_id)
        : undefined);
    return (
      <TurnCard
        characterName={character ?? null}
        entry={entry}
        fresh={fresh}
        key={entry.id}
      />
    );
  }
  if (entry.kind === "mode") {
    return <ModeMarquee entry={entry} key={entry.id} />;
  }
  if (entry.kind === "tarot") {
    return <TarotReveal entry={entry} key={entry.id} />;
  }
  if (entry.kind === "fail") {
    return (
      <article className="fail-banner" key={entry.id}>
        <AlertTriangle aria-hidden="true" size={14} />
        <span>{entry.message}</span>
      </article>
    );
  }
  return null;
}

function ViewToggle({
  view,
  setView,
}: {
  view: StageView;
  setView: (next: StageView) => void;
}) {
  return (
    <>
      <button
        className={`stage__filter${view === "transcript" ? " is-active" : ""}`}
        onClick={() => setView("transcript")}
        type="button"
      >
        <ScrollText aria-hidden="true" size={12} />
        Transcript
      </button>
      <button
        className={`stage__filter${view === "bus" ? " is-active" : ""}`}
        onClick={() => setView("bus")}
        type="button"
      >
        <Bookmark aria-hidden="true" size={12} />
        Bus
      </button>
    </>
  );
}

function FilterToggle({
  filter,
  setFilter,
}: {
  filter: TranscriptFilter;
  setFilter: (next: TranscriptFilter) => void;
}) {
  const cycle: TranscriptFilter[] = ["all", "narrative", "mechanics"];
  const label: Record<TranscriptFilter, string> = {
    all: "All",
    narrative: "Prose",
    mechanics: "Mechanics",
  };
  const current = cycle.indexOf(filter);
  return (
    <button
      className="stage__filter"
      onClick={() => setFilter(cycle[(current + 1) % cycle.length])}
      type="button"
      title="Cycle filter"
    >
      <Filter aria-hidden="true" size={12} />
      {label[filter]}
    </button>
  );
}
