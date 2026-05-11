import { MessageSquare, ScrollText, Send } from "lucide-react";
import { useMemo, useState } from "react";

import { useSessionStore } from "../store/sessionStore";
import type { TurnRecord } from "../types";
import { classNames, formatTime, shortText } from "../utils";

type LogMode = "messages" | "narrations";

export function MessageLog() {
  const [mode, setMode] = useState<LogMode>("messages");
  const messages = useSessionStore((state) => state.messages);
  const turns = useSessionStore((state) => state.turns);
  const narrations = useMemo(
    () => [...turns].sort((a, b) => a.turn_id - b.turn_id),
    [turns],
  );
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
              <NarrationCard key={turn.turn_id} turn={turn} />
            ))}
            {narrations.length === 0 && (
              <div className="empty-state">No narrations</div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function NarrationCard({ turn }: { turn: TurnRecord }) {
  const fullText = turn.markdown || turn.prose;
  return (
    <article className="message-card narration-card" title={fullText}>
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
