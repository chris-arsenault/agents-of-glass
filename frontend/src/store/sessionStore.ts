import { useMemo } from "react";
import { create } from "zustand";

import {
  fetchCampaigns,
  fetchCampaignFile,
  fetchFileSection,
  fetchLive,
  fetchSceneIndex,
  fetchSummary,
  fetchTable,
  fetchTurnRange,
} from "../api";
import { getConfig } from "../config";
import { sectionTerms } from "../sections";
import type {
  CampaignListItem,
  CharacterRecord,
  ClockRecord,
  DmSurfacePayload,
  EventRecord,
  FileContent,
  FileEntry,
  GraphSnapshot,
  LiveCursors,
  MessageRecord,
  RollRecord,
  RuntimeState,
  SceneIndexActive,
  SceneIndexArc,
  SceneTrackerRecord,
  TablePayload,
  TarotRecord,
  TurnRecord,
} from "../types";
import { fileMatches } from "../utils";

const earlierTurnsWindow = 50;
const aroundTurnRadius = 25;
const maxMessages = 400;
const maxEvents = 300;
const maxRolls = 200;
const emptyFiles: FileEntry[] = [];
const emptyTable: TablePayload = { index: null, scene: null, files: [] };
const emptyDmSurface: DmSurfacePayload = {
  current_scene: null,
  beats: [],
  files: [],
};
const emptyGraph: GraphSnapshot = {
  available: false,
  target: "",
  entities: [],
  edges: [],
  entity_types: [],
};
const initialCursors: LiveCursors = {
  turn: null,
  messages: null,
  events: null,
  rolls: null,
};
const campaignStorageKey = "agents-of-glass:selected-campaign";

interface SessionStore {
  campaigns: CampaignListItem[];
  campaignId: string;
  playerOrder: string[];
  activeSection: string;
  generatedAt: string | null;
  runtime: RuntimeState | null;
  characters: CharacterRecord[];
  turns: TurnRecord[];
  messages: MessageRecord[];
  events: EventRecord[];
  rolls: RollRecord[];
  clocks: ClockRecord[];
  sceneTrackers: SceneTrackerRecord[];
  tarot: TarotRecord[];
  graph: GraphSnapshot;
  table: TablePayload;
  dmSurface: DmSurfacePayload;
  cursors: LiveCursors;
  fileLists: Record<string, FileEntry[]>;
  selectedFile: FileContent | null;
  sceneIndex: SceneIndexArc[];
  sceneIndexActive: SceneIndexActive | null;
  isBootstrapping: boolean;
  isPolling: boolean;
  isFileLoading: boolean;
  isLoadingEarlierTurns: boolean;
  isLoadingTurnRange: boolean;
  hasMoreEarlierTurns: boolean;
  error: string | null;
  databaseError: string | null;
  bootstrap: () => Promise<void>;
  pollLive: () => Promise<void>;
  refreshCurrentState: () => Promise<void>;
  setCampaign: (campaignId: string) => Promise<void>;
  setActiveSection: (section: string) => Promise<void>;
  loadFile: (path: string) => Promise<void>;
  loadEarlierTurns: () => Promise<number>;
  loadSceneIndex: () => Promise<void>;
  loadTurnsAround: (turnId: number) => Promise<void>;
}

type CampaignDataState = Pick<
  SessionStore,
  | "generatedAt"
  | "runtime"
  | "characters"
  | "turns"
  | "messages"
  | "events"
  | "rolls"
  | "clocks"
  | "sceneTrackers"
  | "tarot"
  | "graph"
  | "table"
  | "dmSurface"
  | "cursors"
  | "fileLists"
  | "selectedFile"
  | "sceneIndex"
  | "sceneIndexActive"
  | "databaseError"
>;

function emptyCampaignData(): CampaignDataState {
  return {
    generatedAt: null,
    runtime: null,
    characters: [],
    turns: [],
    messages: [],
    events: [],
    rolls: [],
    clocks: [],
    sceneTrackers: [],
    tarot: [],
    graph: emptyGraph,
    table: emptyTable,
    dmSurface: emptyDmSurface,
    cursors: { ...initialCursors },
    fileLists: {},
    selectedFile: null,
    sceneIndex: [],
    sceneIndexActive: null,
    databaseError: null,
  };
}

async function fetchCampaignSnapshot(
  campaignId: string,
  activeSection: string,
): Promise<CampaignDataState> {
  const [summary, table, live, files, scenes] = await Promise.all([
    fetchSummary(campaignId),
    fetchTable(campaignId),
    fetchLive(campaignId, {}),
    fetchFileSection(campaignId, activeSection),
    fetchSceneIndex(campaignId),
  ]);
  return {
    runtime: summary.runtime,
    characters: summary.characters,
    clocks: summary.clocks,
    sceneTrackers: summary.scene_trackers,
    tarot: summary.tarot,
    graph: summary.graph,
    table: table.table,
    dmSurface: summary.dm_surface ?? emptyDmSurface,
    turns: live.turns,
    messages: live.messages,
    events: live.events,
    rolls: live.rolls,
    cursors: live.cursors,
    generatedAt: live.generated_at,
    fileLists: { [activeSection]: files.files },
    selectedFile: null,
    sceneIndex: scenes.arcs,
    sceneIndexActive: scenes.active,
    databaseError:
      summary.database_error ??
      live.database_error ??
      scenes.database_error ??
      null,
  };
}

export const useSessionStore = create<SessionStore>((set, get) => {
  const config = getConfig();
  return {
    campaigns: [],
    campaignId: "",
    playerOrder: config.playerOrder,
    activeSection: "journal",
    generatedAt: null,
    runtime: null,
    characters: [],
    turns: [],
    messages: [],
    events: [],
    rolls: [],
    clocks: [],
    sceneTrackers: [],
    tarot: [],
    graph: emptyGraph,
    table: emptyTable,
    dmSurface: emptyDmSurface,
    cursors: initialCursors,
    fileLists: {},
    selectedFile: null,
    sceneIndex: [],
    sceneIndexActive: null,
    isBootstrapping: false,
    isPolling: false,
    isFileLoading: false,
    isLoadingEarlierTurns: false,
    isLoadingTurnRange: false,
    hasMoreEarlierTurns: true,
    error: null,
    databaseError: null,
    bootstrap: async () => {
      const { campaignId, activeSection } = get();
      set({ isBootstrapping: true, isFileLoading: true, error: null });
      try {
        const campaigns = sortCampaigns((await fetchCampaigns()).campaigns);
        const nextCampaignId = chooseCampaignId(campaigns, campaignId);
        if (!nextCampaignId) {
          set({
            campaigns,
            campaignId: "",
            ...emptyCampaignData(),
          });
          return;
        }
        rememberCampaignId(nextCampaignId);
        const data = await fetchCampaignSnapshot(nextCampaignId, activeSection);
        set({
          campaigns,
          campaignId: nextCampaignId,
          ...data,
          hasMoreEarlierTurns: hasEarlierTurns(data.turns),
        });
      } catch (err) {
        set({ error: messageFromError(err) });
      } finally {
        set({ isBootstrapping: false, isFileLoading: false });
      }
    },
    pollLive: async () => {
      const { campaignId, cursors } = get();
      if (!campaignId) {
        return;
      }
      set({ isPolling: true, error: null });
      try {
        const live = await fetchLive(campaignId, cursors, {
          includeState: true,
        });
        const introducesNewScene = sceneIndexNeedsRefresh(
          get().sceneIndex,
          live.turns,
        );
        set((state) => ({
          runtime: live.runtime ?? state.runtime,
          clocks: live.clocks ?? state.clocks,
          sceneTrackers: live.scene_trackers ?? state.sceneTrackers,
          tarot: live.tarot ?? state.tarot,
          dmSurface: live.dm_surface ?? state.dmSurface,
          turns: mergeTurns(state.turns, live.turns),
          messages: mergeByKey(
            state.messages,
            live.messages,
            "id",
            maxMessages,
          ),
          events: mergeByKey(state.events, live.events, "event_id", maxEvents),
          rolls: mergeByKey(state.rolls, live.rolls, "roll_id", maxRolls),
          cursors: live.cursors,
          generatedAt: live.generated_at,
          databaseError: live.database_error ?? state.databaseError,
        }));
        if (introducesNewScene) {
          void get().loadSceneIndex();
        }
      } catch (err) {
        set({ error: messageFromError(err) });
      } finally {
        set({ isPolling: false });
      }
    },
    refreshCurrentState: async () => {
      const { campaignId } = get();
      if (!campaignId) {
        await get().bootstrap();
        return;
      }
      set({ isPolling: true, error: null });
      try {
        const [campaignsResponse, summary, table, live, scenes] =
          await Promise.all([
            fetchCampaigns(),
            fetchSummary(campaignId),
            fetchTable(campaignId),
            fetchLive(campaignId, get().cursors, { includeState: true }),
            fetchSceneIndex(campaignId),
          ]);
        set((state) => ({
          campaigns: sortCampaigns(campaignsResponse.campaigns),
          runtime: live.runtime ?? summary.runtime,
          characters: summary.characters,
          clocks: live.clocks ?? summary.clocks,
          sceneTrackers: live.scene_trackers ?? summary.scene_trackers,
          tarot: live.tarot ?? summary.tarot,
          graph: summary.graph,
          table: table.table,
          dmSurface: live.dm_surface ?? summary.dm_surface ?? emptyDmSurface,
          turns: mergeTurns(state.turns, live.turns),
          messages: mergeByKey(
            state.messages,
            live.messages,
            "id",
            maxMessages,
          ),
          events: mergeByKey(state.events, live.events, "event_id", maxEvents),
          rolls: mergeByKey(state.rolls, live.rolls, "roll_id", maxRolls),
          cursors: live.cursors,
          generatedAt: live.generated_at,
          sceneIndex: scenes.arcs,
          sceneIndexActive: scenes.active,
          databaseError:
            summary.database_error ??
            live.database_error ??
            scenes.database_error ??
            null,
        }));
      } catch (err) {
        set({ error: messageFromError(err) });
      } finally {
        set({ isPolling: false });
      }
    },
    setCampaign: async (campaignId: string) => {
      const nextCampaignId = campaignId.trim();
      if (!nextCampaignId || nextCampaignId === get().campaignId) {
        return;
      }
      rememberCampaignId(nextCampaignId);
      const { activeSection } = get();
      set({
        campaignId: nextCampaignId,
        isBootstrapping: true,
        isFileLoading: true,
        error: null,
        ...emptyCampaignData(),
        hasMoreEarlierTurns: true,
      });
      try {
        const data = await fetchCampaignSnapshot(nextCampaignId, activeSection);
        set({ ...data, hasMoreEarlierTurns: hasEarlierTurns(data.turns) });
      } catch (err) {
        set({ error: messageFromError(err) });
      } finally {
        set({ isBootstrapping: false, isFileLoading: false });
      }
    },
    setActiveSection: async (section: string) => {
      set({ activeSection: section, error: null });
      const { campaignId } = get();
      if (!campaignId) {
        return;
      }
      if (get().fileLists[section]) {
        return;
      }
      set({ isFileLoading: true });
      try {
        const response = await fetchFileSection(campaignId, section);
        set((state) => ({
          fileLists: { ...state.fileLists, [section]: response.files },
        }));
      } catch (err) {
        set({ error: messageFromError(err) });
      } finally {
        set({ isFileLoading: false });
      }
    },
    loadFile: async (path: string) => {
      const { campaignId } = get();
      if (!campaignId) {
        return;
      }
      set({ isFileLoading: true, error: null });
      try {
        const selectedFile = await fetchCampaignFile(campaignId, path);
        set({ selectedFile });
      } catch (err) {
        set({ error: messageFromError(err) });
      } finally {
        set({ isFileLoading: false });
      }
    },
    loadEarlierTurns: async () => {
      const { campaignId, turns, isLoadingEarlierTurns, hasMoreEarlierTurns } =
        get();
      if (
        !campaignId ||
        isLoadingEarlierTurns ||
        !hasMoreEarlierTurns ||
        turns.length === 0
      ) {
        return 0;
      }
      const oldest = turns[0].turn_id;
      if (oldest <= 1) {
        set({ hasMoreEarlierTurns: false });
        return 0;
      }
      const toTurn = oldest - 1;
      const fromTurn = Math.max(1, toTurn - earlierTurnsWindow + 1);
      set({ isLoadingEarlierTurns: true, error: null });
      try {
        const response = await fetchTurnRange(campaignId, fromTurn, toTurn);
        const fetched = response.items.length;
        set((state) => {
          const merged = mergeTurns(state.turns, response.items);
          const reachedStart = fromTurn <= 1;
          return {
            turns: merged,
            hasMoreEarlierTurns:
              !reachedStart && fetched > 0 && hasEarlierTurns(merged),
            databaseError: response.database_error ?? state.databaseError,
          };
        });
        return fetched;
      } catch (err) {
        set({ error: messageFromError(err) });
        return 0;
      } finally {
        set({ isLoadingEarlierTurns: false });
      }
    },
    loadSceneIndex: async () => {
      const { campaignId } = get();
      if (!campaignId) {
        return;
      }
      try {
        const scenes = await fetchSceneIndex(campaignId);
        set({
          sceneIndex: scenes.arcs,
          sceneIndexActive: scenes.active,
          databaseError: scenes.database_error ?? get().databaseError,
        });
      } catch (err) {
        set({ error: messageFromError(err) });
      }
    },
    loadTurnsAround: async (turnId: number) => {
      const { campaignId, turns, isLoadingTurnRange } = get();
      if (!campaignId || isLoadingTurnRange) {
        return;
      }
      if (turns.some((turn) => turn.turn_id === turnId)) {
        return;
      }
      const fromTurn = Math.max(1, turnId - aroundTurnRadius);
      const toTurn = turnId + aroundTurnRadius;
      set({ isLoadingTurnRange: true, error: null });
      try {
        const response = await fetchTurnRange(campaignId, fromTurn, toTurn);
        set((state) => ({
          turns: mergeTurns(state.turns, response.items),
          hasMoreEarlierTurns: hasEarlierTurns(
            mergeTurns(state.turns, response.items),
          ),
          databaseError: response.database_error ?? state.databaseError,
        }));
      } catch (err) {
        set({ error: messageFromError(err) });
      } finally {
        set({ isLoadingTurnRange: false });
      }
    },
  };
});

export function selectActiveFiles(state: SessionStore): FileEntry[] {
  return state.fileLists[state.activeSection] ?? emptyFiles;
}

export function selectLatestDmTurn(
  state: SessionStore,
): TurnRecord | undefined {
  return state.turns
    .filter((turn) => turn.role === "dm" || turn.speaker === "dm")
    .at(-1);
}

export function selectPlayerIds(state: SessionStore): string[] {
  const extras = state.characters
    .map((character) => character.player_id)
    .filter((id) => !state.playerOrder.includes(id));
  return [...state.playerOrder, ...extras].slice(0, 4);
}

/** Stable-reference hook for the resolved player id list. */
export function usePlayerIds(): string[] {
  const playerOrder = useSessionStore((state) => state.playerOrder);
  const characters = useSessionStore((state) => state.characters);
  return useMemo(() => {
    const extras = characters
      .map((character) => character.player_id)
      .filter((id) => !playerOrder.includes(id));
    return [...playerOrder, ...extras].slice(0, 4);
  }, [characters, playerOrder]);
}

export function selectCharacterForPlayer(
  state: SessionStore,
  playerId: string,
): CharacterRecord | undefined {
  return state.characters.find((character) => character.player_id === playerId);
}

export function selectLatestTurnForPlayer(
  state: SessionStore,
  playerId: string,
): TurnRecord | undefined {
  const character = selectCharacterForPlayer(state, playerId);
  return state.turns
    .filter(
      (turn) =>
        turn.speaker === playerId ||
        (character && turn.character_id === character.character_id),
    )
    .at(-1);
}

export function selectLatestRollForPlayer(
  state: SessionStore,
  playerId: string,
): RollRecord | undefined {
  const character = selectCharacterForPlayer(state, playerId);
  return state.rolls
    .filter(
      (roll) =>
        roll.actor === playerId ||
        (character && roll.character_id === character.character_id),
    )
    .at(-1);
}

export function selectTarotForPlayer(
  state: SessionStore,
  playerId: string,
): TarotRecord | undefined {
  const character = selectCharacterForPlayer(state, playerId);
  return state.tarot
    .filter(
      (card) =>
        card.actor === playerId || card.actor === character?.character_id,
    )
    .at(-1);
}

export function selectFilesForPlayer(
  state: SessionStore,
  playerId: string,
): FileEntry[] {
  const character = selectCharacterForPlayer(state, playerId);
  const terms = [playerId, character?.character_id, character?.name]
    .filter((value): value is string => Boolean(value))
    .map((value) => value.toLowerCase());
  return Object.values(state.fileLists)
    .flat()
    .filter((file) => fileMatches(file, terms));
}

export function selectSectionCount(
  state: SessionStore,
  section: string,
): number {
  const loaded = state.fileLists[section];
  if (loaded) {
    return loaded.length;
  }
  const terms = sectionTerms[section] ?? [section];
  return Object.values(state.fileLists)
    .flat()
    .filter((file) => fileMatches(file, terms)).length;
}

function hasEarlierTurns(turns: TurnRecord[]): boolean {
  return turns.length > 0 && turns[0].turn_id > 1;
}

function sceneIndexNeedsRefresh(
  index: SceneIndexArc[],
  incomingTurns: TurnRecord[],
): boolean {
  if (incomingTurns.length === 0) {
    return false;
  }
  const known = new Set<string>();
  for (const arc of index) {
    for (const scene of arc.scenes) {
      known.add(`${arc.arc_id ?? ""}::${scene.scene_id ?? ""}`);
    }
  }
  return incomingTurns.some(
    (turn) => !known.has(`${turn.arc_id ?? ""}::${turn.scene_id ?? ""}`),
  );
}

function mergeTurns(
  current: TurnRecord[],
  incoming: TurnRecord[],
): TurnRecord[] {
  if (incoming.length === 0) {
    return current;
  }
  const byId = new Map<number, TurnRecord>();
  for (const turn of current) {
    byId.set(turn.turn_id, turn);
  }
  let changed = current.length !== byId.size;
  for (const turn of incoming) {
    const prior = byId.get(turn.turn_id);
    if (prior !== turn) {
      changed = true;
    }
    byId.set(turn.turn_id, turn);
  }
  if (!changed) {
    return current;
  }
  return Array.from(byId.values()).sort((a, b) => a.turn_id - b.turn_id);
}

function mergeByKey<T extends object, K extends keyof T>(
  current: T[],
  incoming: T[],
  key: K,
  maxItems: number,
): T[] {
  if (incoming.length === 0) {
    return current;
  }
  const byKey = new Map<unknown, T>();
  for (const item of current) {
    byKey.set(item[key] as PropertyKey, item);
  }
  for (const item of incoming) {
    byKey.set(item[key] as PropertyKey, item);
  }
  return Array.from(byKey.values()).slice(-maxItems);
}

function sortCampaigns(campaigns: CampaignListItem[]): CampaignListItem[] {
  return [...campaigns].sort((a, b) => {
    const byUpdated = b.updated_at.localeCompare(a.updated_at);
    return byUpdated || a.campaign_id.localeCompare(b.campaign_id);
  });
}

function chooseCampaignId(
  campaigns: CampaignListItem[],
  currentCampaignId: string,
): string {
  const ids = new Set(campaigns.map((campaign) => campaign.campaign_id));
  const storedCampaignId = readStoredCampaignId();
  if (currentCampaignId && ids.has(currentCampaignId)) {
    return currentCampaignId;
  }
  if (storedCampaignId && ids.has(storedCampaignId)) {
    return storedCampaignId;
  }
  return campaigns[0]?.campaign_id ?? "";
}

function readStoredCampaignId(): string | null {
  try {
    return window.localStorage.getItem(campaignStorageKey);
  } catch {
    return null;
  }
}

function rememberCampaignId(campaignId: string): void {
  try {
    window.localStorage.setItem(campaignStorageKey, campaignId);
  } catch {
    return;
  }
}

function messageFromError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
