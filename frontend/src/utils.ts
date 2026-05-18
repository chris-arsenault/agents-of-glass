import type { FileEntry } from "./types";

export function classNames(
  ...values: Array<string | false | null | undefined>
): string {
  return values.filter(Boolean).join(" ");
}

export function formatTime(value?: string | null): string {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function progressPercent(value: number, max: number): number {
  if (max <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((value / max) * 100)));
}

export function shortText(
  text: string | null | undefined,
  maxLength = 240,
): string {
  if (!text) {
    return "";
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength).trim()}...`;
}

export function fileMatches(entry: FileEntry, terms: string[]): boolean {
  const haystack =
    `${entry.path} ${entry.title} ${entry.section}`.toLowerCase();
  return terms.some((term) => haystack.includes(term));
}

export function prettifyTitle(slug: string | null | undefined): string {
  if (!slug) {
    return "";
  }
  return slug
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
