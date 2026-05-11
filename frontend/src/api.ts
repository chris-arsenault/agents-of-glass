import { getConfig } from "./config";
import type {
  FileContent,
  FileListPayload,
  LiveCursors,
  LivePayload,
  SummaryPayload,
  TableResourcePayload,
  TurnOutputPayload,
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const { apiBaseUrl } = getConfig();
  const baseUrl = apiBaseUrl.replace(/\/$/, "");
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export function fetchSummary(campaignId: string): Promise<SummaryPayload> {
  return getJson<SummaryPayload>(
    `/v1/campaigns/${encodeURIComponent(campaignId)}/summary`,
  );
}

export function fetchTable(campaignId: string): Promise<TableResourcePayload> {
  return getJson<TableResourcePayload>(
    `/v1/campaigns/${encodeURIComponent(campaignId)}/table`,
  );
}

export function fetchLive(
  campaignId: string,
  cursors: Partial<LiveCursors>,
  options: { includeState?: boolean } = {},
): Promise<LivePayload> {
  const params = new URLSearchParams();
  if (cursors.turn !== undefined && cursors.turn !== null) {
    params.set("after_turn", String(cursors.turn));
  }
  if (cursors.messages) {
    params.set("messages_after", cursors.messages);
  }
  if (cursors.events) {
    params.set("events_after", cursors.events);
  }
  if (cursors.rolls) {
    params.set("rolls_after", cursors.rolls);
  }
  if (options.includeState) {
    params.set("include_state", "1");
  }
  const query = params.toString();
  const querySuffix = query ? `?${query}` : "";
  return getJson<LivePayload>(
    `/v1/campaigns/${encodeURIComponent(campaignId)}/live${querySuffix}`,
  );
}

export function fetchFileSection(
  campaignId: string,
  section: string,
): Promise<FileListPayload> {
  const encodedCampaign = encodeURIComponent(campaignId);
  const params = new URLSearchParams({ section, limit: "1000" });
  return getJson<FileListPayload>(
    `/v1/campaigns/${encodedCampaign}/files?${params.toString()}`,
  );
}

export function fetchCampaignFiles(
  campaignId: string,
): Promise<FileListPayload> {
  const encodedCampaign = encodeURIComponent(campaignId);
  const params = new URLSearchParams({ all: "1", limit: "5000" });
  return getJson<FileListPayload>(
    `/v1/campaigns/${encodedCampaign}/files?${params.toString()}`,
  );
}

export function fetchCampaignFile(
  campaignId: string,
  path: string,
): Promise<FileContent> {
  const encodedCampaign = encodeURIComponent(campaignId);
  const params = new URLSearchParams({ path });
  return getJson<FileContent>(
    `/v1/campaigns/${encodedCampaign}/files?${params.toString()}`,
  );
}

export function fetchTurnOutput(campaignId: string): Promise<TurnOutputPayload> {
  return getJson<TurnOutputPayload>(
    `/v1/campaigns/${encodeURIComponent(campaignId)}/turn-output`,
  );
}
