import { MessageSquare, Send } from "lucide-react";

import { useSessionStore } from "../store/sessionStore";
import { formatTime } from "../utils";

export function MessageLog() {
  const messages = useSessionStore((state) => state.messages);
  return (
    <aside className="message-log">
      <header className="panel-header panel-header--compact">
        <div>
          <p className="eyebrow">Message Bus</p>
          <h2>All Channels</h2>
        </div>
        <MessageSquare aria-hidden="true" size={19} />
      </header>
      <div className="message-list">
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
      </div>
    </aside>
  );
}
