import { CircleDot, RefreshCcw, Terminal } from "lucide-react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { fetchTurnOutput } from "../api";
import { AGENT_DISPLAY, toneFor } from "../agentChroma";
import { useSessionStore } from "../store/sessionStore";
import type { TurnOutputPayload } from "../types";
import { classNames, formatTime } from "../utils";

const POLL_MS = 2000;

type Stream = "stdout" | "stderr" | "both";

export function TurnOutputView() {
  const campaignId = useSessionStore((state) => state.campaignId);

  const [payload, setPayload] = useState<TurnOutputPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [stream, setStream] = useState<Stream>("both");
  const [autoscroll, setAutoscroll] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const next = await fetchTurnOutput(campaignId);
      setPayload(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    void refresh();
    const handle = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(handle);
  }, [refresh]);

  const bodyRef = useRef<HTMLDivElement | null>(null);
  useLayoutEffect(() => {
    if (!autoscroll || !bodyRef.current) return;
    bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [autoscroll, payload]);

  const onScroll = useCallback(() => {
    const node = bodyRef.current;
    if (!node) return;
    const atBottom =
      node.scrollHeight - node.scrollTop - node.clientHeight < 24;
    setAutoscroll(atBottom);
  }, []);

  const tone = toneFor(payload?.speaker);
  const status = (payload?.status ?? "ready").toLowerCase();
  const active = Boolean(payload?.active);

  return (
    <section className="terminal" aria-label="Active turn output">
      <header className="terminal__head">
        <div className="terminal__head-title">
          <span className="terminal__head-eyebrow">Live tap</span>
          <span className="terminal__head-name">Turn output</span>
        </div>
        <div className="terminal__meta">
          <span
            className={classNames(
              "terminal__status",
              active && "is-active",
              status,
            )}
          >
            <CircleDot aria-hidden="true" size={10} />
            <span>{active ? "ACTIVE" : status.toUpperCase() || "IDLE"}</span>
          </span>
          {payload?.speaker && (
            <span className="terminal__speaker" data-tone={tone}>
              <span className="terminal__speaker-dot" aria-hidden="true" />
              {AGENT_DISPLAY[tone] ?? payload.speaker}
              {payload.role ? ` · ${payload.role}` : ""}
            </span>
          )}
          {payload?.turn_id != null && (
            <span className="terminal__chip">turn {payload.turn_id}</span>
          )}
          {payload?.turn_number != null && (
            <span className="terminal__chip">#{payload.turn_number}</span>
          )}
          <span className="terminal__chip">
            {formatBytes(
              (payload?.stdout_bytes ?? 0) + (payload?.stderr_bytes ?? 0),
            )}
          </span>
          <span className="terminal__chip">
            {payload?.updated_at
              ? `updated ${formatTime(payload.updated_at)}`
              : payload?.generated_at
                ? `polled ${formatTime(payload.generated_at)}`
                : ""}
          </span>
          <div className="terminal__streams" role="tablist">
            <StreamButton current={stream} setStream={setStream} value="both" />
            <StreamButton
              current={stream}
              setStream={setStream}
              value="stdout"
            />
            <StreamButton
              current={stream}
              setStream={setStream}
              value="stderr"
            />
          </div>
          <button
            aria-label="Refresh"
            className="terminal__refresh"
            onClick={() => void refresh()}
            type="button"
          >
            <RefreshCcw aria-hidden="true" size={13} />
          </button>
        </div>
      </header>
      {error && (
        <div className="status-banner" style={{ margin: "8px 20px 0" }}>
          {error}
        </div>
      )}
      <div className="terminal__body" onScroll={onScroll} ref={bodyRef}>
        {loading && !payload ? (
          <div className="terminal__loading">
            <Terminal aria-hidden="true" size={14} /> connecting…
          </div>
        ) : !payload || (!payload.stdout && !payload.stderr) ? (
          <div className="terminal__loading">
            {active
              ? "Waiting for output…"
              : "No active turn. The terminal is silent."}
          </div>
        ) : (
          <pre className="terminal__pre">
            {renderStreams(payload, stream)}
          </pre>
        )}
      </div>
      <footer className="terminal__foot">
        <span>
          {payload?.turn_dir ? `turn_dir: ${payload.turn_dir}` : "no turn dir"}
        </span>
        <span style={{ flex: 1 }} />
        <span>{autoscroll ? "autoscrolling" : "scroll paused"}</span>
        <span>·</span>
        <span>poll {POLL_MS / 1000}s</span>
      </footer>
    </section>
  );
}

function StreamButton({
  current,
  setStream,
  value,
}: {
  current: Stream;
  setStream: (next: Stream) => void;
  value: Stream;
}) {
  return (
    <button
      className={classNames(
        "terminal__streams-button",
        current === value && "is-active",
      )}
      onClick={() => setStream(value)}
      type="button"
    >
      {value}
    </button>
  );
}

function renderStreams(payload: TurnOutputPayload, stream: Stream) {
  const parts: Array<{ key: string; text: string; kind: Stream }> = [];
  if ((stream === "both" || stream === "stdout") && payload.stdout) {
    parts.push({ key: "stdout", text: payload.stdout, kind: "stdout" });
  }
  if ((stream === "both" || stream === "stderr") && payload.stderr) {
    parts.push({ key: "stderr", text: payload.stderr, kind: "stderr" });
  }
  if (parts.length === 0) {
    return <span className="terminal__dim">— no data on this stream —</span>;
  }
  return parts.flatMap((part, idx) => {
    const lines = part.text.split("\n");
    const result = lines.map((line, i) => (
      <span
        className={classNames("terminal__line", `terminal__line--${part.kind}`)}
        key={`${part.key}-${i}`}
      >
        {line || " "}
        {"\n"}
      </span>
    ));
    if (idx < parts.length - 1) {
      result.push(
        <span className="terminal__divider" key={`${part.key}-div`}>
          {`\n── ${parts[idx + 1].kind} ──\n\n`}
        </span>,
      );
    }
    return result;
  });
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / (1024 * 1024)).toFixed(2)}MB`;
}
