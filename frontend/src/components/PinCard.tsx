import type { LucideIcon } from "lucide-react";
import { FileText, Sparkles } from "lucide-react";

interface PinCardProps {
  kind: string;
  title: string;
  sub?: string;
  excerpt?: string;
  icon?: LucideIcon;
  onOpen?: () => void;
}

export function PinCard({
  kind,
  title,
  sub,
  excerpt,
  icon: Icon = FileText,
  onOpen,
}: PinCardProps) {
  return (
    <button className="pin-card" onClick={onOpen} type="button">
      <header className="pin-card__head">
        <Icon aria-hidden="true" size={12} />
        <span>{kind}</span>
      </header>
      <span className="pin-card__title">{title}</span>
      {sub && <span className="pin-card__sub">{sub}</span>}
      {excerpt && <p className="pin-card__excerpt">{excerpt}</p>}
    </button>
  );
}

PinCard.Sparkles = Sparkles;
