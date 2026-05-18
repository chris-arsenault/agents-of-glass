import {
  AlertTriangle,
  Bookmark,
  Filter,
  MessagesSquare,
  ScrollText,
} from "lucide-react";
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useSessionStore } from "../store/sessionStore";
import {
  buildInterleavedStream,
  buildMessageStream,
  buildTranscriptStream,
  type TranscriptFilter,
  type TranscriptTimelineEntry,
} from "../transcriptModel";
import { MessageCard } from "./MessageCard";
import { ModeMarquee } from "./ModeMarquee";
import { TarotReveal } from "./TarotReveal";
import { TurnCard } from "./TurnCard";

type StageView = "transcript" | "interleaved" | "bus";

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
  const loadEarlierTurns = useSessionStore((state) => state.loadEarlierTurns);
  const loadTurnsAround = useSessionStore((state) => state.loadTurnsAround);
  const isLoadingEarlierTurns = useSessionStore(
    (state) => state.isLoadingEarlierTurns,
  );
  const hasMoreEarlierTurns = useSessionStore(
    (state) => state.hasMoreEarlierTurns,
  );

  const [view, setView] = useState<StageView>("transcript");
  const [filter, setFilter] = useState<TranscriptFilter>("all");

  const stream = useMemo(
    () => buildTranscriptStream({ turns, events, tarot, rolls, filter }),
    [turns, events, tarot, rolls, filter],
  );
  const messageStream = useMemo(() => buildMessageStream(messages), [messages]);
  const interleavedStream = useMemo(
    () => buildInterleavedStream({ turns, events, tarot, rolls, messages, filter }),
    [turns, events, tarot, rolls, messages, filter],
  );
  const visibleEntries = useMemo(() => {
    if (view === "bus") {
      return messageStream;
    }
    if (view === "interleaved") {
      return interleavedStream;
    }
    return stream;
  }, [interleavedStream, messageStream, stream, view]);

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
  const firstEntryIdRef = useRef<string | null>(null);
  const freshEntryIdRef = useRef<string | null>(null);
  const lastViewRef = useRef<StageView>(view);
  const prependAnchorRef = useRef<{ height: number; top: number } | null>(null);

  // Capture scroll metrics before a prepend, so we can restore visual position.
  useLayoutEffect(() => {
    const node = scrollRef.current;
    const first = visibleEntries.at(0);
    if (!node || !first) {
      return;
    }
    if (
      firstEntryIdRef.current !== null &&
      firstEntryIdRef.current !== first.id &&
      prependAnchorRef.current
    ) {
      const { height, top } = prependAnchorRef.current;
      const delta = node.scrollHeight - height;
      if (delta > 0) {
        node.scrollTop = top + delta;
      }
      prependAnchorRef.current = null;
    }
    firstEntryIdRef.current = first.id;
  }, [visibleEntries]);

  // Autoscroll on new entries at the bottom.
  useLayoutEffect(() => {
    const last = visibleEntries.at(-1);
    if (!last) {
      return;
    }
    if (lastViewRef.current !== view) {
      lastViewRef.current = view;
      lastEntryIdRef.current = last.id;
      freshEntryIdRef.current = null;
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
  }, [view, visibleEntries]);

  // Auto-load earlier turns when the user scrolls near the top.
  useEffect(() => {
    if (view !== "transcript" && view !== "interleaved") {
      return;
    }
    const node = scrollRef.current;
    if (!node) {
      return;
    }
    const onScroll = () => {
      if (!hasMoreEarlierTurns || isLoadingEarlierTurns) {
        return;
      }
      if (node.scrollTop <= 80) {
        prependAnchorRef.current = {
          height: node.scrollHeight,
          top: node.scrollTop,
        };
        void loadEarlierTurns().then((fetched) => {
          if (!fetched) {
            prependAnchorRef.current = null;
          }
        });
      }
    };
    node.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      node.removeEventListener("scroll", onScroll);
    };
  }, [hasMoreEarlierTurns, isLoadingEarlierTurns, loadEarlierTurns, view]);

  // Jump-to-turn (from agent lane click, cmd-k, or timeline navigator).
  useEffect(() => {
    if (jumpTurnId === null) return;
    const node = scrollRef.current;
    if (!node) return;
    const target = node.querySelector(`[data-turn-id="${jumpTurnId}"]`);
    if (target instanceof HTMLElement) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("is-fresh");
      window.setTimeout(() => target.classList.remove("is-fresh"), 1600);
      onJumpHandled();
      return;
    }
    // Target turn isn't loaded yet; fetch a window around it and re-run via deps.
    void loadTurnsAround(jumpTurnId);
  }, [jumpTurnId, loadTurnsAround, onJumpHandled, visibleEntries]);

  return (
    <section className="stage" aria-label="Transcript">
      <StageHeader
        filter={filter}
        setFilter={setFilter}
        setView={setView}
        view={view}
      />
      <div className="stage__transcript" ref={scrollRef}>
        {view !== "bus" && (
          <EarlierTurnsBanner
            hasMore={hasMoreEarlierTurns}
            isLoading={isLoadingEarlierTurns}
            firstTurnId={turns.at(0)?.turn_id ?? null}
            onLoad={() => {
              const node = scrollRef.current;
              if (node) {
                prependAnchorRef.current = {
                  height: node.scrollHeight,
                  top: node.scrollTop,
                };
              }
              void loadEarlierTurns();
            }}
          />
        )}
        {visibleEntries.length === 0 ? (
          <div className="empty-state">
            {view === "bus"
              ? "No bus traffic."
              : view === "interleaved"
                ? "No transcript or bus entries yet."
                : "No transcript entries yet."}
          </div>
        ) : (
          visibleEntries.map((entry) => (
            renderEntry(
              entry,
              characterByPlayer,
              freshEntryIdRef.current === entry.id,
            )
          ))
        )}
      </div>
    </section>
  );
}

function renderEntry(
  entry: TranscriptTimelineEntry,
  characterByPlayer: Map<string, string>,
  fresh: boolean,
) {
  if (entry.kind === "message") {
    return (
      <MessageCard fresh={fresh} key={entry.id} message={entry.message} />
    );
  }
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

function StageHeader({
  filter,
  setFilter,
  setView,
  view,
}: {
  filter: TranscriptFilter;
  setFilter: (next: TranscriptFilter) => void;
  setView: (next: StageView) => void;
  view: StageView;
}) {
  const headerCopy: Record<StageView, { eyebrow: string; name: string }> = {
    transcript: { eyebrow: "Conclave transcript", name: "Live ledger" },
    interleaved: { eyebrow: "Interleaved ledger", name: "Turns + bus traffic" },
    bus: { eyebrow: "Message bus", name: "Inter-agent comms" },
  };
  const copy = headerCopy[view];
  return (
    <header className="stage__head">
      <div className="stage__head-title">
        <span className="stage__head-eyebrow">{copy.eyebrow}</span>
        <span className="stage__head-name">{copy.name}</span>
      </div>
      <div className="stage__head-controls" role="tablist">
        <ViewToggle view={view} setView={setView} />
        {view !== "bus" && (
          <FilterToggle filter={filter} setFilter={setFilter} />
        )}
      </div>
    </header>
  );
}

function EarlierTurnsBanner({
  hasMore,
  isLoading,
  firstTurnId,
  onLoad,
}: {
  hasMore: boolean;
  isLoading: boolean;
  firstTurnId: number | null;
  onLoad: () => void;
}) {
  if (isLoading) {
    return (
      <div className="transcript__earlier transcript__earlier--loading">
        Loading earlier turns…
      </div>
    );
  }
  if (!hasMore) {
    if (firstTurnId === null || firstTurnId > 1) {
      return null;
    }
    return (
      <div className="transcript__earlier transcript__earlier--start">
        Start of campaign.
      </div>
    );
  }
  return (
    <button
      className="transcript__earlier transcript__earlier--button"
      onClick={onLoad}
      type="button"
    >
      Load earlier turns
    </button>
  );
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
        className={`stage__filter${view === "interleaved" ? " is-active" : ""}`}
        onClick={() => setView("interleaved")}
        type="button"
      >
        <MessagesSquare aria-hidden="true" size={12} />
        Mixed
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
