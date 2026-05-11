import { Send } from "lucide-react";

import { sigilFor, toneFor } from "../agentChroma";
import type { MessageRecord } from "../types";
import { formatTime } from "../utils";

export function MessageCard({ message }: { message: MessageRecord }) {
  const tone = toneFor(message.sender);
  const sigil = sigilFor(message.sender);
  return (
    <article className="message-card" data-tone={tone}>
      <span className="message-card__stripe" aria-hidden="true" />
      <div className="message-card__body">
        <header className="message-card__head">
          <span className="message-card__type">{message.type}</span>
          <span className="message-card__route">
            <span aria-hidden="true" style={{ fontFamily: "var(--font-mono)", fontSize: 9 }}>
              {sigil}
            </span>
            <span>{message.sender}</span>
            <Send aria-hidden="true" size={11} />
            <span>{message.recipient}</span>
          </span>
          <span className="message-card__time">{formatTime(message.created_at)}</span>
        </header>
        <p className="message-card__text">{message.body}</p>
      </div>
    </article>
  );
}
