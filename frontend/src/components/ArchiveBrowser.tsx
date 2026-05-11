import {
  AlertTriangle,
  Bug,
  FileText,
  Folder,
  Search,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type MouseEvent,
} from "react";

import { fetchCampaignFiles } from "../api";
import {
  buildFolderEntries,
  documentCategories,
  filesInFolder,
  filterBySearch,
  folderLabel,
  prefixFromLocation,
  sortFiles,
  syncFolderToUrl,
  visibleDocuments,
  type DocumentCategory,
  type FolderEntry,
  type SortMode,
} from "../documentBrowserModel";
import { useSessionStore } from "../store/sessionStore";
import type { FileEntry } from "../types";
import { classNames, formatTime } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";

interface ArchiveBrowserProps {
  error: string | null;
}

export function ArchiveBrowser({ error }: ArchiveBrowserProps) {
  const campaignId = useSessionStore((state) => state.campaignId);
  const selectedFile = useSessionStore((state) => state.selectedFile);
  const isFileLoading = useSessionStore((state) => state.isFileLoading);
  const loadFile = useSessionStore((state) => state.loadFile);

  const [files, setFiles] = useState<FileEntry[]>([]);
  const [activeFolder, setActiveFolder] = useState(() => prefixFromLocation());
  const [category, setCategory] = useState<DocumentCategory>("all");
  const [query, setQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("path");
  const [showDebug, setShowDebug] = useState(false);
  const [includeNested, setIncludeNested] = useState(false);
  const [browserError, setBrowserError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchCampaignFiles(campaignId)
      .then((response) => {
        if (!cancelled) {
          setFiles(response.files);
          setBrowserError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setBrowserError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [campaignId]);

  useEffect(() => {
    const onPop = () => setActiveFolder(prefixFromLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const docs = useMemo(
    () => visibleDocuments(files, { category, showDebug }),
    [category, files, showDebug],
  );
  const folders = useMemo(() => buildFolderEntries(docs), [docs]);
  const listed = useMemo(
    () =>
      sortFiles(
        filterBySearch(filesInFolder(docs, activeFolder, includeNested), query),
        sortMode,
      ),
    [activeFolder, docs, includeNested, query, sortMode],
  );

  const onFolderClick = useCallback(
    (event: MouseEvent<HTMLButtonElement>) => {
      const folder = event.currentTarget.dataset.folder ?? "";
      setActiveFolder(folder);
      syncFolderToUrl(folder);
    },
    [],
  );

  const onFileClick = useCallback(
    (event: MouseEvent<HTMLButtonElement>) => {
      const path = event.currentTarget.dataset.path;
      if (path) {
        void loadFile(path);
      }
    },
    [loadFile],
  );

  const combinedError = error ?? browserError;

  return (
    <section className="archive" aria-label="Echo Ledger archive">
      <ArchiveColumn
        category={category}
        files={docs}
        folders={folders}
        activeFolder={activeFolder}
        onCategoryChange={(value) => setCategory(value)}
        onFolderClick={onFolderClick}
        showDebug={showDebug}
        setShowDebug={setShowDebug}
      />
      <ArchiveList
        activeFolder={activeFolder}
        files={listed}
        includeNested={includeNested}
        loading={loading}
        onFileClick={onFileClick}
        onQueryChange={setQuery}
        onSortChange={setSortMode}
        query={query}
        selectedPath={selectedFile?.path}
        setIncludeNested={setIncludeNested}
        sortMode={sortMode}
        totalFiles={docs.length}
      />
      <ArchiveViewer
        error={combinedError}
        file={selectedFile}
        loading={isFileLoading}
      />
    </section>
  );
}

function ArchiveColumn({
  activeFolder,
  category,
  files,
  folders,
  onCategoryChange,
  onFolderClick,
  setShowDebug,
  showDebug,
}: {
  activeFolder: string;
  category: DocumentCategory;
  files: FileEntry[];
  folders: FolderEntry[];
  onCategoryChange: (value: DocumentCategory) => void;
  onFolderClick: (event: MouseEvent<HTMLButtonElement>) => void;
  setShowDebug: (value: boolean) => void;
  showDebug: boolean;
}) {
  return (
    <aside className="archive__column">
      <header className="archive__column-head">
        <div>
          <div className="archive__column-eyebrow">Echo Ledger</div>
          <div className="archive__column-name">Folders</div>
        </div>
        <Folder aria-hidden="true" size={16} />
      </header>
      <div className="archive__controls">
        <label className="archive__select">
          <Folder aria-hidden="true" size={12} />
          <select
            onChange={(event) =>
              onCategoryChange(event.target.value as DocumentCategory)
            }
            value={category}
          >
            {documentCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <div className="archive__checks">
          <label className="archive__check">
            <input
              checked={showDebug}
              onChange={(event) => setShowDebug(event.target.checked)}
              type="checkbox"
            />
            <Bug aria-hidden="true" size={11} />
            <span>Debug</span>
          </label>
          <span>{files.length} files</span>
        </div>
      </div>
      <div className="archive__list">
        {folders.map((folder) => (
          <button
            className={classNames(
              "archive__folder",
              activeFolder === folder.path && "is-active",
            )}
            data-folder={folder.path}
            key={folder.path || "root"}
            onClick={onFolderClick}
            type="button"
            title={folder.path || "campaign root"}
            style={{ paddingLeft: `${10 + folder.depth * 12}px` }}
          >
            <Folder aria-hidden="true" size={12} />
            <strong>{folder.label}</strong>
            <em>{folder.count}</em>
          </button>
        ))}
      </div>
    </aside>
  );
}

function ArchiveList({
  activeFolder,
  files,
  includeNested,
  loading,
  onFileClick,
  onQueryChange,
  onSortChange,
  query,
  selectedPath,
  setIncludeNested,
  sortMode,
  totalFiles,
}: {
  activeFolder: string;
  files: FileEntry[];
  includeNested: boolean;
  loading: boolean;
  onFileClick: (event: MouseEvent<HTMLButtonElement>) => void;
  onQueryChange: (value: string) => void;
  onSortChange: (value: SortMode) => void;
  query: string;
  selectedPath?: string;
  setIncludeNested: (value: boolean) => void;
  sortMode: SortMode;
  totalFiles: number;
}) {
  return (
    <section className="archive__column">
      <header className="archive__column-head">
        <div>
          <div className="archive__column-eyebrow">
            {activeFolder || "campaign root"}
          </div>
          <div className="archive__column-name">{folderLabel(activeFolder)}</div>
        </div>
        <span className="archive__column-meta">
          {loading ? "loading" : `${files.length}/${totalFiles}`}
        </span>
      </header>
      <div className="archive__controls">
        <label className="archive__search">
          <Search aria-hidden="true" size={12} />
          <input
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              onQueryChange(event.target.value)
            }
            placeholder="Filter title or path"
            type="search"
            value={query}
          />
        </label>
        <label className="archive__select">
          <select
            onChange={(event: ChangeEvent<HTMLSelectElement>) =>
              onSortChange(event.target.value as SortMode)
            }
            value={sortMode}
          >
            <option value="path">Sort · Path</option>
            <option value="title">Sort · Title</option>
            <option value="updated-desc">Sort · Newest</option>
            <option value="updated-asc">Sort · Oldest</option>
            <option value="size-desc">Sort · Largest</option>
          </select>
        </label>
        <div className="archive__checks">
          <label className="archive__check">
            <input
              checked={includeNested}
              onChange={(event) => setIncludeNested(event.target.checked)}
              type="checkbox"
            />
            <span>Nested</span>
          </label>
        </div>
      </div>
      <div className="archive__list">
        {files.length === 0 ? (
          <div className="empty-state">No documents.</div>
        ) : (
          files.map((file) => (
            <button
              className={classNames(
                "archive__file",
                selectedPath === file.path && "is-active",
              )}
              data-path={file.path}
              key={file.path}
              onClick={onFileClick}
              title={file.path}
              type="button"
            >
              <FileText aria-hidden="true" size={13} />
              <div>
                <div className="archive__file-title">
                  {file.title || file.name}
                </div>
                <div className="archive__file-path">{file.path}</div>
              </div>
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function ArchiveViewer({
  error,
  file,
  loading,
}: {
  error: string | null;
  file: ReturnType<typeof useSessionStore.getState>["selectedFile"];
  loading: boolean;
}) {
  return (
    <section className="archive__viewer">
      <header className="archive__viewer-head">
        <div className="archive__viewer-title">
          <span className="rail__eyebrow">Document</span>
          <span className="archive__viewer-name">
            {file?.title || "Select a document"}
          </span>
          {file && <span className="archive__viewer-path">{file.path}</span>}
        </div>
        <span className="archive__column-meta">
          {loading ? "loading…" : file ? formatTime(file.updated_at) : ""}
        </span>
      </header>
      {error && (
        <div className="status-banner">
          <AlertTriangle aria-hidden="true" size={14} />
          <span>{error}</span>
        </div>
      )}
      <div className="archive__viewer-body">
        {file ? (
          <MarkdownBlock content={file.content} />
        ) : (
          <div className="empty-state">
            Pick a folder, then a file. The Echo Ledger holds every authored
            line.
          </div>
        )}
      </div>
    </section>
  );
}
