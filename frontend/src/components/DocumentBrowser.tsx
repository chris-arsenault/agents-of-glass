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

interface DocumentBrowserProps {
  error: string | null;
}

export function DocumentBrowser({ error }: DocumentBrowserProps) {
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
  const [isLoadingFiles, setIsLoadingFiles] = useState(true);

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
        if (!cancelled) {
          setIsLoadingFiles(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [campaignId]);

  useEffect(() => {
    const handlePopState = () => setActiveFolder(prefixFromLocation());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const documentFiles = useMemo(
    () => visibleDocuments(files, { category, showDebug }),
    [category, files, showDebug],
  );
  const folderEntries = useMemo(
    () => buildFolderEntries(documentFiles),
    [documentFiles],
  );
  const listedFiles = useMemo(
    () =>
      sortFiles(
        filterBySearch(
          filesInFolder(documentFiles, activeFolder, includeNested),
          query,
        ),
        sortMode,
      ),
    [activeFolder, documentFiles, includeNested, query, sortMode],
  );
  const selectedDocument = listedFiles.some(
    (file) => file.path === selectedFile?.path,
  )
    ? selectedFile
    : null;
  const combinedError = error ?? browserError;

  const handleFolderClick = useCallback(
    (event: MouseEvent<HTMLButtonElement>) => {
      const folder = event.currentTarget.dataset.folder ?? "";
      setActiveFolder(folder);
      syncFolderToUrl(folder);
    },
    [],
  );
  const handleFileClick = useCallback(
    (event: MouseEvent<HTMLButtonElement>) => {
      const path = event.currentTarget.dataset.path;
      if (path) {
        void loadFile(path);
      }
    },
    [loadFile],
  );
  const handleCategoryChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      setCategory(event.target.value as DocumentCategory);
    },
    [],
  );
  const handleSortChange = useCallback((event: ChangeEvent<HTMLSelectElement>) => {
    setSortMode(event.target.value as SortMode);
  }, []);
  const handleQueryChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
  }, []);

  return (
    <section className="documents-stage">
      {combinedError && <DocumentError message={combinedError} />}
      <FolderTree
        activeFolder={activeFolder}
        category={category}
        files={documentFiles}
        folders={folderEntries}
        onCategoryChange={handleCategoryChange}
        onFolderClick={handleFolderClick}
        setShowDebug={setShowDebug}
        showDebug={showDebug}
      />
      <DocumentList
        activeFolder={activeFolder}
        files={listedFiles}
        includeNested={includeNested}
        isLoadingFiles={isLoadingFiles}
        onFileClick={handleFileClick}
        onQueryChange={handleQueryChange}
        onSortChange={handleSortChange}
        query={query}
        selectedPath={selectedDocument?.path}
        setIncludeNested={setIncludeNested}
        sortMode={sortMode}
        totalFiles={documentFiles.length}
      />
      <article className="document-viewer panel">
        <header className="panel-header panel-header--compact">
          <div>
            <p className="eyebrow">{selectedDocument?.path ?? "Document"}</p>
            <h2>{selectedDocument?.title ?? folderLabel(activeFolder)}</h2>
          </div>
          <div className="header-actions">
            <span>
              {isFileLoading ? "loading" : formatTime(selectedDocument?.updated_at)}
            </span>
          </div>
        </header>
        <MarkdownBlock
          content={selectedDocument?.content}
          emptyLabel="Select a document"
        />
      </article>
    </section>
  );
}

function DocumentError({ message }: { message: string }) {
  return (
    <div className="status-banner status-banner--global">
      <AlertTriangle aria-hidden="true" size={17} />
      <span>{message}</span>
    </div>
  );
}

function FolderTree({
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
  onCategoryChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  onFolderClick: (event: MouseEvent<HTMLButtonElement>) => void;
  setShowDebug: (value: boolean) => void;
  showDebug: boolean;
}) {
  return (
    <aside className="document-sections panel">
      <header className="panel-header panel-header--compact">
        <div>
          <p className="eyebrow">Documents</p>
          <h2>Folders</h2>
        </div>
        <Folder aria-hidden="true" size={19} />
      </header>
      <div className="document-filter-block">
        <label>
          <span>Scope</span>
          <select onChange={onCategoryChange} value={category}>
            {documentCategories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="document-check">
          <input
            checked={showDebug}
            onChange={(event) => setShowDebug(event.target.checked)}
            type="checkbox"
          />
          <Bug aria-hidden="true" size={14} />
          <span>Show debug artifacts</span>
        </label>
        <small>{files.length} browsable files</small>
      </div>
      <div className="document-folder-list">
        {folders.map((folder) => (
          <button
            className={classNames(
              "document-folder-button",
              `folder-depth-${Math.min(folder.depth, 6)}`,
              activeFolder === folder.path && "is-active",
            )}
            data-folder={folder.path}
            key={folder.path || "root"}
            onClick={onFolderClick}
            title={folder.path || "campaign root"}
            type="button"
          >
            <Folder aria-hidden="true" size={15} />
            <span>{folder.label}</span>
            <strong>{folder.count}</strong>
          </button>
        ))}
      </div>
    </aside>
  );
}

function DocumentList({
  activeFolder,
  files,
  includeNested,
  isLoadingFiles,
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
  isLoadingFiles: boolean;
  onFileClick: (event: MouseEvent<HTMLButtonElement>) => void;
  onQueryChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSortChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  query: string;
  selectedPath?: string | null;
  setIncludeNested: (value: boolean) => void;
  sortMode: SortMode;
  totalFiles: number;
}) {
  return (
    <section className="document-list-panel panel">
      <header className="panel-header panel-header--compact">
        <div>
          <p className="eyebrow">{activeFolder || "campaign root"}</p>
          <h2>{folderLabel(activeFolder)}</h2>
        </div>
        <div className="header-actions">
          <span>{isLoadingFiles ? "loading" : `${files.length}/${totalFiles}`}</span>
        </div>
      </header>
      <div className="document-controls">
        <label className="document-search">
          <Search aria-hidden="true" size={15} />
          <input
            onChange={onQueryChange}
            placeholder="Filter title or path"
            type="search"
            value={query}
          />
        </label>
        <select onChange={onSortChange} value={sortMode}>
          <option value="path">Path</option>
          <option value="title">Title</option>
          <option value="updated-desc">Newest</option>
          <option value="updated-asc">Oldest</option>
          <option value="size-desc">Largest</option>
        </select>
        <label className="document-check document-check--compact">
          <input
            checked={includeNested}
            onChange={(event) => setIncludeNested(event.target.checked)}
            type="checkbox"
          />
          <span>Nested</span>
        </label>
      </div>
      <div className="document-file-list">
        {files.map((file) => (
          <button
            className={classNames(
              "document-file-button",
              selectedPath === file.path && "is-active",
            )}
            data-path={file.path}
            key={file.path}
            onClick={onFileClick}
            title={file.path}
            type="button"
          >
            <FileText aria-hidden="true" size={15} />
            <span>{file.title || file.name}</span>
            <small>{file.path}</small>
          </button>
        ))}
        {files.length === 0 && (
          <div className="empty-state empty-state--small">No documents</div>
        )}
      </div>
    </section>
  );
}
