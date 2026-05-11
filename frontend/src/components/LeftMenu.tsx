import {
  BookOpen,
  Clock,
  FileText,
  LucideIcon,
  Map,
  ScrollText,
  Shield,
} from "lucide-react";

import { selectSectionCount, useSessionStore } from "../store/sessionStore";
import { classNames } from "../utils";

const sections: Array<{ id: string; label: string; icon: LucideIcon }> = [
  { id: "journal", label: "Journal", icon: BookOpen },
  { id: "lore", label: "Lore", icon: Map },
  { id: "arcs", label: "Arcs", icon: Clock },
  { id: "scenes", label: "Scenes", icon: ScrollText },
  { id: "dm", label: "DM", icon: Shield },
  { id: "audit", label: "Audit", icon: FileText },
];

export function LeftMenu() {
  const activeSection = useSessionStore((state) => state.activeSection);
  const setActiveSection = useSessionStore((state) => state.setActiveSection);
  const counts = useSessionStore((state) =>
    Object.fromEntries(
      sections.map((section) => [
        section.id,
        selectSectionCount(state, section.id),
      ]),
    ),
  );
  return (
    <nav className="left-menu" aria-label="Campaign sections">
      <div className="left-menu__mark">AoG</div>
      <div className="left-menu__items">
        {sections.map((section) => {
          const Icon = section.icon;
          return (
            <button
              aria-label={section.label}
              className={classNames(
                "left-menu__button",
                activeSection === section.id && "is-active",
              )}
              key={section.id}
              onClick={() => void setActiveSection(section.id)}
              title={section.label}
              type="button"
            >
              <Icon aria-hidden="true" size={20} />
              <span>{counts[section.id]}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
