import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

interface ModalProps {
  children: ReactNode;
  isOpen: boolean;
  onClose: () => void;
  subtitle?: string | null;
  title: string;
}

export function Modal({
  children,
  isOpen,
  onClose,
  subtitle,
  title,
}: ModalProps) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);
  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-backdrop">
      <button
        aria-label="Close modal"
        className="modal-lightbox"
        onClick={onClose}
        type="button"
      />
      <section aria-modal="true" className="modal-panel" role="dialog">
        <header className="modal-header">
          <div>
            <p className="eyebrow">{subtitle ?? "Document"}</p>
            <h2>{title}</h2>
          </div>
          <button
            aria-label="Close modal"
            className="icon-button"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
      </section>
    </div>
  );
}
