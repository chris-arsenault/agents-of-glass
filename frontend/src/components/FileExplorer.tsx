import { FileText } from "lucide-react";

import type { FileEntry } from "../types";
import { classNames } from "../utils";

interface FileExplorerProps {
  files: FileEntry[];
  selectedPath?: string | null;
  title: string;
  emptyLabel?: string;
  limit?: number;
  onSelect: (path: string) => void;
}

export function FileExplorer({
  files,
  selectedPath,
  title,
  emptyLabel = "No files",
  limit = 8,
  onSelect,
}: FileExplorerProps) {
  const visible = files.slice(0, limit);
  return (
    <section className="file-explorer">
      <div className="mini-header">
        <span>{title}</span>
        <small>{files.length}</small>
      </div>
      <div className="file-list">
        {visible.map((file) => (
          <button
            className={classNames(
              "file-button",
              selectedPath === file.path && "is-active",
            )}
            key={file.path}
            onClick={() => onSelect(file.path)}
            title={file.path}
            type="button"
          >
            <FileText aria-hidden="true" size={15} />
            <span>{file.title || file.name}</span>
          </button>
        ))}
        {visible.length === 0 && (
          <div className="empty-state empty-state--small">{emptyLabel}</div>
        )}
      </div>
    </section>
  );
}
