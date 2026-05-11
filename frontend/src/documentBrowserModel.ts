import type { FileEntry } from "./types";

export type DocumentCategory =
  | "all"
  | "campaign"
  | "players"
  | "dm"
  | "arcs"
  | "reference"
  | "table"
  | "debug";
export type SortMode = "path" | "title" | "updated-desc" | "updated-asc" | "size-desc";

export interface FolderEntry {
  path: string;
  label: string;
  depth: number;
  count: number;
}

export const documentCategories: Array<{
  id: DocumentCategory;
  label: string;
}> = [
  { id: "all", label: "All" },
  { id: "campaign", label: "Campaign" },
  { id: "players", label: "Players" },
  { id: "dm", label: "DM" },
  { id: "arcs", label: "Arcs" },
  { id: "reference", label: "Reference" },
  { id: "table", label: "Table" },
  { id: "debug", label: "Debug" },
];

export function visibleDocuments(
  files: FileEntry[],
  options: { category: DocumentCategory; showDebug: boolean },
): FileEntry[] {
  return files.filter((file) => {
    if (isNarrationOrTurnPrompt(file.path)) {
      return false;
    }
    if (isDebugArtifact(file.path) && !options.showDebug) {
      return false;
    }
    return matchesCategory(file.path, options.category);
  });
}

export function buildFolderEntries(files: FileEntry[]): FolderEntry[] {
  const folders = new Set<string>([""]);
  for (const file of files) {
    const parts = file.path.split("/").slice(0, -1);
    for (let index = 1; index <= parts.length; index += 1) {
      folders.add(parts.slice(0, index).join("/"));
    }
  }
  return Array.from(folders)
    .sort(compareFolders)
    .map((path) => ({
      path,
      label: folderLabel(path),
      depth: path ? path.split("/").length : 0,
      count: files.filter((file) => file.path.startsWith(pathPrefix(path))).length,
    }));
}

export function filesInFolder(
  files: FileEntry[],
  folder: string,
  includeNested: boolean,
): FileEntry[] {
  const prefix = pathPrefix(folder);
  return files.filter((file) => {
    if (!file.path.startsWith(prefix)) {
      return false;
    }
    if (includeNested || !folder) {
      return true;
    }
    return parentFolder(file.path) === folder;
  });
}

export function filterBySearch(files: FileEntry[], query: string): FileEntry[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return files;
  }
  return files.filter((file) =>
    `${file.path} ${file.title} ${file.name}`.toLowerCase().includes(needle),
  );
}

export function sortFiles(files: FileEntry[], sortMode: SortMode): FileEntry[] {
  return [...files].sort((a, b) => {
    if (sortMode === "title") {
      return (a.title || a.name).localeCompare(b.title || b.name);
    }
    if (sortMode === "updated-desc") {
      return Date.parse(b.updated_at) - Date.parse(a.updated_at);
    }
    if (sortMode === "updated-asc") {
      return Date.parse(a.updated_at) - Date.parse(b.updated_at);
    }
    if (sortMode === "size-desc") {
      return b.size - a.size;
    }
    return a.path.localeCompare(b.path);
  });
}

export function prefixFromLocation(): string {
  return normalizeFolder(new URLSearchParams(window.location.search).get("prefix"));
}

export function syncFolderToUrl(folder: string) {
  const params = new URLSearchParams(window.location.search);
  if (folder) {
    params.set("prefix", folder);
  } else {
    params.delete("prefix");
  }
  const query = params.toString();
  const nextPath = query ? `/documents?${query}` : "/documents";
  window.history.pushState({}, "", nextPath);
}

export function folderLabel(path: string): string {
  if (!path) {
    return "Campaign root";
  }
  return path.split("/").at(-1) ?? path;
}

function matchesCategory(path: string, category: DocumentCategory): boolean {
  if (category === "all") {
    return true;
  }
  if (category === "debug") {
    return isDebugArtifact(path);
  }
  if (category === "campaign") {
    return (
      path.startsWith("shared/") ||
      ["README.md", "context.md", "summary.md", "scene-framing.md"].includes(path)
    );
  }
  if (category === "players") {
    return path.startsWith("players/");
  }
  if (category === "dm") {
    return path.startsWith("dm/");
  }
  if (category === "arcs") {
    return path.startsWith("arcs/");
  }
  if (category === "reference") {
    return ["instructions/", "methodologies/", "how-to/", "srd/"].some((prefix) =>
      path.startsWith(prefix),
    );
  }
  return path.startsWith("table/");
}

function isNarrationOrTurnPrompt(path: string): boolean {
  return (
    isTurnArtifact(path, ["in.md", "out.md"]) ||
    path === "transcript.md" ||
    path.endsWith("/transcript.md")
  );
}

function isDebugArtifact(path: string): boolean {
  return (
    path === "audit.jsonl" ||
    path.endsWith("/audit.jsonl") ||
    isTurnArtifact(path, ["COMMIT.md", "agent-stderr.txt", "agent-stdout.txt"])
  );
}

function isTurnArtifact(path: string, names: string[]): boolean {
  const parts = path.split("/");
  if (parts.length < 3 || !names.includes(parts.at(-1) ?? "")) {
    return false;
  }
  return parts.at(-3) === "turns" && /^\d+$/.test(parts.at(-2) ?? "");
}

function normalizeFolder(value: string | null): string {
  return (value ?? "").split("/").filter(Boolean).join("/");
}

function pathPrefix(path: string): string {
  return path ? `${path}/` : "";
}

function parentFolder(path: string): string {
  return path.split("/").slice(0, -1).join("/");
}

function compareFolders(a: string, b: string): number {
  if (a === "") {
    return -1;
  }
  if (b === "") {
    return 1;
  }
  return a.localeCompare(b);
}
