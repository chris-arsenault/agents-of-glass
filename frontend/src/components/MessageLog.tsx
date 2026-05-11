import { MessageSquare, ScrollText, Send } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
  type RefCallback,
  type SyntheticEvent,
} from "react";

import { useSessionStore } from "../store/sessionStore";
import type { TurnRecord } from "../types";
import { classNames, formatTime, shortText } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";

type LogMode = "messages" | "narrations";

export function MessageLog() {
  const [mode, setMode] = useState<LogMode>("messages");
  const [activeNarrationId, setActiveNarrationId] = useState<number | null>(
    null,
  );
  const popoverRef = useRef<HTMLElement | null>(null);
  const hideTimerRef = useRef<number | null>(null);
  const messages = useSessionStore((state) => state.messages);
  const turns = useSessionStore((state) => state.turns);
  const narrations = useMemo(
    () => [...turns].sort((a, b) => a.turn_id - b.turn_id),
    [turns],
  );
  const activeNarration = useMemo(
    () =>
      mode === "narrations"
        ? narrations.find((turn) => turn.turn_id === activeNarrationId)
        : undefined,
    [activeNarrationId, mode, narrations],
  );
  const clearHideTimer = useCallback(() => {
    if (hideTimerRef.current !== null) {
      window.clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  }, []);
  const scheduleHide = useCallback(() => {
    clearHideTimer();
    hideTimerRef.current = window.setTimeout(() => {
      setActiveNarrationId(null);
      hideTimerRef.current = null;
    }, 120);
  }, [clearHideTimer]);
  useEffect(() => () => clearHideTimer(), [clearHideTimer]);
  const setPopoverRef = useCallback((node: HTMLElement | null) => {
    popoverRef.current = node;
  }, []);
  const handleNarrationEnter = useCallback(
    (event: SyntheticEvent<HTMLElement>) => {
      const turnId = Number(event.currentTarget.dataset.turnId);
      if (Number.isFinite(turnId)) {
        clearHideTimer();
        setActiveNarrationId(turnId);
      }
    },
    [clearHideTimer],
  );
  const handleNarrationLeave = useCallback(
    (event: MouseEvent<HTMLElement>) => {
      const nextTarget = event.relatedTarget;
      if (
        nextTarget instanceof Node &&
        popoverRef.current?.contains(nextTarget)
      ) {
        return;
      }
      scheduleHide();
    },
    [scheduleHide],
  );
  const handlePopoverLeave = useCallback(() => scheduleHide(), [scheduleHide]);

  return (
    <aside className="message-log">
      <header className="panel-header panel-header--compact">
        <div>
          <p className="eyebrow">{mode === "messages" ? "Message Bus" : "Narrations"}</p>
          <h2>{mode === "messages" ? "All Channels" : "Turn Order"}</h2>
        </div>
        <div className="log-toggle" role="tablist" aria-label="Right pane view">
          <button
            aria-selected={mode === "messages"}
            className={classNames(mode === "messages" && "is-active")}
            onClick={() => setMode("messages")}
            role="tab"
            title="Messages"
            type="button"
          >
            <MessageSquare aria-hidden="true" size={16} />
            <span>Messages</span>
          </button>
          <button
            aria-selected={mode === "narrations"}
            className={classNames(mode === "narrations" && "is-active")}
            onClick={() => setMode("narrations")}
            role="tab"
            title="Narrations"
            type="button"
          >
            <ScrollText aria-hidden="true" size={16} />
            <span>Narrations</span>
          </button>
        </div>
      </header>
      <div className="message-list">
        {mode === "messages" ? (
          <>
            {messages.map((message) => (
              <article className="message-card" key={message.id}>
                <div className="message-card__meta">
                  <span>{formatTime(message.created_at)}</span>
                  <strong>{message.type}</strong>
                </div>
                <div className="message-card__route">
                  <span>{message.sender}</span>
                  <Send aria-hidden="true" size={13} />
                  <span>{message.recipient}</span>
                </div>
                <p>{message.body}</p>
              </article>
            ))}
            {messages.length === 0 && (
              <div className="empty-state">No messages</div>
            )}
          </>
        ) : (
          <>
            {narrations.map((turn) => (
              <NarrationCard
                key={turn.turn_id}
                onMouseEnter={handleNarrationEnter}
                onMouseLeave={handleNarrationLeave}
                turn={turn}
              />
            ))}
            {narrations.length === 0 && (
              <div className="empty-state">No narrations</div>
            )}
          </>
        )}
      </div>
      {activeNarration && (
        <NarrationPopover
          onMouseEnter={clearHideTimer}
          onMouseLeave={handlePopoverLeave}
          setPopoverRef={setPopoverRef}
          turn={activeNarration}
        />
      )}
    </aside>
  );
}

function NarrationCard({
  onMouseEnter,
  onMouseLeave,
  turn,
}: {
  onMouseEnter: (event: SyntheticEvent<HTMLElement>) => void;
  onMouseLeave: (event: MouseEvent<HTMLElement>) => void;
  turn: TurnRecord;
}) {
  const fullText = turn.markdown || turn.prose;
  return (
    <article
      className="message-card narration-card"
      data-turn-id={turn.turn_id}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="message-card__meta">
        <span>{formatTime(turn.created_at || turn.ts)}</span>
        <strong>Turn {turn.turn_id}</strong>
      </div>
      <div className="message-card__route">
        <span>{turn.speaker}</span>
        <ScrollText aria-hidden="true" size={13} />
        <span>{turn.scene_id ?? turn.mode}</span>
      </div>
      <p>{shortText(fullText, 420)}</p>
    </article>
  );
}

const NarrationPopover = function NarrationPopover({
  onMouseEnter,
  onMouseLeave,
  setPopoverRef,
  turn,
}: {
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  setPopoverRef: RefCallback<HTMLElement>;
  turn: TurnRecord;
}) {
  const fullText = turn.markdown || turn.prose;
  return (
    <section
      className="narration-popover"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      ref={setPopoverRef}
    >
      <header>
        <div>
          <p className="eyebrow">Full Narration</p>
          <h3>Turn {turn.turn_id}</h3>
        </div>
        <span>{turn.speaker}</span>
      </header>
      <MarkdownBlock content={fullText} emptyLabel="No narration text" compact />
    </section>
  );
};
