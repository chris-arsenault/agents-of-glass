import {
  Activity,
  Compass,
  FileText,
  MonitorPlay,
  Sparkles,
  Swords,
  Terminal,
  Waves,
} from "lucide-react";
import { useMemo } from "react";
import type { LucideIcon } from "lucide-react";

import { AGENT_DISPLAY, toneFor } from "../agentChroma";
import {
  usePlayerIds,
  useSessionStore,
} from "../store/sessionStore";
import { classNames } from "../utils";

type AppRoute = "live" | "archive" | "output";

const ROUTES: Array<{ id: AppRoute; label: string; icon: LucideIcon }> = [
  { id: "live", label: "Live", icon: MonitorPlay },
  { id: "archive", label: "Archive", icon: FileText },
  { id: "output", label: "Output", icon: Terminal },
];

const MODE_ICON: Record<string, LucideIcon> = {
  combat: Swords,
  chase: Waves,
  "social-pressure": Compass,
  "scene-play": Sparkles,
  prelude: Sparkles,
};

interface LeftMenuProps {
  activeRoute: AppRoute;
  onNavigate: (route: AppRoute) => void;
  onOpenCommand: () => void;
}

export function LeftMenu({
  activeRoute,
  onNavigate,
  onOpenCommand,
}: LeftMenuProps) {
  const runtime = useSessionStore((state) => state.runtime);
  const turns = useSessionStore((state) => state.turns);
  const playerIds = usePlayerIds();

  const mode = runtime?.mode_stack?.at(-1) ?? turns.at(-1)?.mode ?? "scene-play";
  const ModeIcon = MODE_ICON[mode] ?? Activity;

  const recentSpeakers = useMemo(() => {
    const window = 6;
    const recent = turns.slice(-window).map((t) => t.speaker);
    return new Set(recent);
  }, [turns]);

  const allAgents = useMemo(() => ["mara", ...playerIds], [playerIds]);

  return (
    <nav className="nav-rail" aria-label="Session navigation">
      <div className="nav-rail__mark" title="Agents of Glass">
        AoG
      </div>
      <div className="nav-rail__turn">
        <span className="nav-rail__turn-label">Turn</span>
        <span className="nav-rail__turn-value">
          {runtime?.turn_counter ?? 0}
        </span>
      </div>
      <div className="nav-rail__mode" title={mode}>
        <ModeIcon aria-hidden="true" size={14} />
        <span>{shortMode(mode)}</span>
      </div>
      <div className="nav-rail__ticker">
        {allAgents.map((agent) => {
          const tone = toneFor(agent);
          const isRecent = recentSpeakers.has(agent);
          return (
            <span
              className={classNames(
                "nav-rail__ticker-row",
                isRecent && "is-recent",
              )}
              data-tone={tone}
              key={agent}
              title={`${AGENT_DISPLAY[tone] ?? agent}${isRecent ? " · recent" : ""}`}
            >
              {AGENT_DISPLAY[tone] ?? agent}
            </span>
          );
        })}
      </div>
      <div className="nav-rail__routes">
        {ROUTES.map((route) => {
          const Icon = route.icon;
          return (
            <button
              aria-label={route.label}
              className={classNames(
                "nav-rail__route",
                activeRoute === route.id && "is-active",
              )}
              key={route.id}
              onClick={() => onNavigate(route.id)}
              type="button"
            >
              <Icon aria-hidden="true" size={16} />
              <span>{route.label}</span>
            </button>
          );
        })}
        <button
          aria-label="Open command palette"
          className="nav-rail__cmdk"
          onClick={onOpenCommand}
          type="button"
        >
          ⌘K
        </button>
      </div>
    </nav>
  );
}

function shortMode(mode: string): string {
  const map: Record<string, string> = {
    "scene-play": "Scene",
    combat: "Combat",
    chase: "Chase",
    "social-pressure": "Social",
    prelude: "Prelude",
  };
  return map[mode] ?? mode.slice(0, 6);
}
