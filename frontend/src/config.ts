import type { AppConfig } from "./types";

declare global {
  interface Window {
    __APP_CONFIG__?: RuntimeConfig;
  }
}

type RuntimeConfig = {
  apiBaseUrl?: string;
  pollIntervalMs?: number | string;
  playerOrder?: string[] | string;
};

const envPlayerOrder = import.meta.env.VITE_PLAYER_ORDER?.split(",")
  .map((value: string) => value.trim())
  .filter(Boolean);

function defaultApiBaseUrl(): string {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  const protocol = window.location.protocol || "http:";
  const hostname = window.location.hostname || "127.0.0.1";
  return `${protocol}//${hostname}:26002`;
}

const defaults: AppConfig = {
  apiBaseUrl: defaultApiBaseUrl(),
  pollIntervalMs: Number(import.meta.env.VITE_POLL_INTERVAL_MS || 120000),
  playerOrder: envPlayerOrder?.length
    ? envPlayerOrder
    : ["tev", "sumi", "renno", "kit"],
};

export function getConfig(): AppConfig {
  const runtime = window.__APP_CONFIG__ ?? {};
  return {
    apiBaseUrl: runtime.apiBaseUrl ?? defaults.apiBaseUrl,
    pollIntervalMs: parsePollInterval(runtime.pollIntervalMs),
    playerOrder: parsePlayerOrder(runtime.playerOrder),
  };
}

function parsePollInterval(value: RuntimeConfig["pollIntervalMs"]): number {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0
      ? parsed
      : defaults.pollIntervalMs;
  }
  return defaults.pollIntervalMs;
}

function parsePlayerOrder(value: RuntimeConfig["playerOrder"]): string[] {
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    return parsed.length ? parsed : defaults.playerOrder;
  }
  return defaults.playerOrder;
}
