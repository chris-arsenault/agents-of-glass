import type { AppConfig } from "./types";

declare global {
  interface Window {
    __APP_CONFIG__?: Partial<AppConfig>;
  }
}

const envPlayerOrder = import.meta.env.VITE_PLAYER_ORDER?.split(",")
  .map((value: string) => value.trim())
  .filter(Boolean);

const defaults: AppConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8765",
  defaultCampaignId: import.meta.env.VITE_DEFAULT_CAMPAIGN_ID || "test-7",
  pollIntervalMs: Number(import.meta.env.VITE_POLL_INTERVAL_MS || 120000),
  playerOrder: envPlayerOrder?.length
    ? envPlayerOrder
    : ["tev", "sumi", "renno", "kit"],
};

export function getConfig(): AppConfig {
  const runtime = window.__APP_CONFIG__ ?? {};
  return {
    ...defaults,
    ...runtime,
    playerOrder: runtime.playerOrder ?? defaults.playerOrder,
  };
}
