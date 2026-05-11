import { FileText, LucideIcon, MonitorPlay } from "lucide-react";

import { classNames } from "../utils";

type AppRoute = "live" | "documents";

const routes: Array<{ id: AppRoute; label: string; icon: LucideIcon }> = [
  { id: "live", label: "Live", icon: MonitorPlay },
  { id: "documents", label: "Docs", icon: FileText },
];

interface LeftMenuProps {
  activeRoute: AppRoute;
  onNavigate: (route: AppRoute) => void;
}

export function LeftMenu({ activeRoute, onNavigate }: LeftMenuProps) {
  return (
    <nav className="left-menu" aria-label="Application views">
      <div className="left-menu__mark">AoG</div>
      <div className="left-menu__items">
        {routes.map((route) => {
          const Icon = route.icon;
          return (
            <button
              aria-label={route.label}
              className={classNames(
                "left-menu__button",
                activeRoute === route.id && "is-active",
              )}
              key={route.id}
              onClick={() => onNavigate(route.id)}
              title={route.label}
              type="button"
            >
              <Icon aria-hidden="true" size={20} />
              <span>{route.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
