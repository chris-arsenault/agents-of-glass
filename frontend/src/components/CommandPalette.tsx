import {
  Compass,
  Drama,
  FileText,
  ListOrdered,
  Search,
  Sparkles,
  Users,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { AGENT_DISPLAY, sigilFor, toneFor } from "../agentChroma";
import {
  usePlayerIds,
  useSessionStore,
} from "../store/sessionStore";
import { shortText } from "../utils";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onJumpTurn: (turnId: number) => void;
  onOpenFile: (path: string) => void;
  onGoTo: (route: "live" | "archive") => void;
}

interface PaletteItem {
  id: string;
  group: string;
  icon: typeof Sparkles;
  label: string;
  sub?: string;
  chip?: string;
  action: () => void;
}

export function CommandPalette({
  isOpen,
  onClose,
  onJumpTurn,
  onOpenFile,
  onGoTo,
}: CommandPaletteProps) {
  const turns = useSessionStore((state) => state.turns);
  const characters = useSessionStore((state) => state.characters);
  const playerIds = usePlayerIds();
  const fileLists = useSessionStore((state) => state.fileLists);

  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setActive(0);
      window.setTimeout(() => inputRef.current?.focus(), 16);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  const items = useMemo<PaletteItem[]>(() => {
    const list: PaletteItem[] = [];
    list.push({
      id: "route-live",
      group: "Routes",
      icon: Sparkles,
      label: "Open Live Ledger",
      sub: "Transcript canvas",
      chip: "live",
      action: () => onGoTo("live"),
    });
    list.push({
      id: "route-archive",
      group: "Routes",
      icon: FileText,
      label: "Open Archive",
      sub: "Echo Ledger document browser",
      chip: "archive",
      action: () => onGoTo("archive"),
    });
    for (const playerId of playerIds) {
      const character = characters.find((c) => c.player_id === playerId);
      const tone = toneFor(playerId);
      list.push({
        id: `player-${playerId}`,
        group: "Characters",
        icon: Users,
        label: character?.name ?? AGENT_DISPLAY[tone] ?? playerId,
        sub: `${AGENT_DISPLAY[tone] ?? playerId} · ${character?.archetype ?? "—"}`,
        chip: sigilFor(playerId),
        action: () => onOpenFile(`players/${playerId}/public/character.md`),
      });
    }
    list.push({
      id: "player-mara",
      group: "Characters",
      icon: Drama,
      label: "Mara",
      sub: "DM persona",
      chip: sigilFor("Mara"),
      action: () => onOpenFile("dm/persona.md"),
    });
    for (const turn of [...turns].reverse().slice(0, 50)) {
      const tone = toneFor(turn.speaker);
      list.push({
        id: `turn-${turn.turn_id}`,
        group: "Turns",
        icon: ListOrdered,
        label: `Turn ${turn.turn_id} · ${AGENT_DISPLAY[tone] ?? turn.speaker}`,
        sub: shortText(turn.markdown || turn.prose, 90),
        chip: turn.scene_id ?? turn.mode,
        action: () => onJumpTurn(turn.turn_id),
      });
    }
    const allFiles = Object.values(fileLists).flat();
    for (const file of allFiles.slice(0, 80)) {
      list.push({
        id: `file-${file.path}`,
        group: "Archive",
        icon: Compass,
        label: file.title || file.name || file.path,
        sub: file.path,
        action: () => onOpenFile(file.path),
      });
    }
    return list;
  }, [
    characters,
    fileLists,
    onGoTo,
    onJumpTurn,
    onOpenFile,
    playerIds,
    turns,
  ]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return items.slice(0, 30);
    }
    return items
      .filter((item) =>
        `${item.label} ${item.sub ?? ""} ${item.chip ?? ""}`
          .toLowerCase()
          .includes(q),
      )
      .slice(0, 50);
  }, [items, query]);

  const grouped = useMemo(() => {
    const map = new Map<string, PaletteItem[]>();
    for (const item of filtered) {
      const existing = map.get(item.group) ?? [];
      existing.push(item);
      map.set(item.group, existing);
    }
    return Array.from(map.entries());
  }, [filtered]);

  const flat = filtered;

  const select = useCallback(
    (idx: number) => {
      const item = flat[idx];
      if (item) {
        item.action();
        onClose();
      }
    },
    [flat, onClose],
  );

  const onInputKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current) => Math.min(flat.length - 1, current + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => Math.max(0, current - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      select(active);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="cmd-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="cmd-panel">
        <header className="cmd-panel__head">
          <Search aria-hidden="true" size={16} />
          <input
            className="cmd-panel__input"
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onInputKey}
            placeholder="Jump · find · open…"
            ref={inputRef}
            value={query}
          />
          <span className="cmd-panel__hint">esc to close</span>
        </header>
        <div className="cmd-panel__list">
          {flat.length === 0 ? (
            <div className="cmd-panel__empty">No matches.</div>
          ) : (
            grouped.map(([group, items]) => (
              <div className="cmd-panel__group" key={group}>
                <div className="cmd-panel__group-label">{group}</div>
                {items.map((item) => {
                  const idx = flat.indexOf(item);
                  const Icon = item.icon;
                  return (
                    <button
                      className={`cmd-row${idx === active ? " is-active" : ""}`}
                      key={item.id}
                      onClick={() => select(idx)}
                      onMouseEnter={() => setActive(idx)}
                      type="button"
                    >
                      <span className="cmd-row__icon" aria-hidden="true">
                        <Icon size={14} />
                      </span>
                      <span className="cmd-row__title">
                        <span className="cmd-row__title-main">
                          {item.label}
                        </span>
                        {item.sub && (
                          <span className="cmd-row__title-sub">{item.sub}</span>
                        )}
                      </span>
                      {item.chip && (
                        <span className="cmd-row__chip">{item.chip}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
