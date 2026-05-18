export interface AppConfig {
  apiBaseUrl: string;
  pollIntervalMs: number;
  playerOrder: string[];
}

export interface CampaignListItem {
  campaign_id: string;
  dashboard_url: string;
  files_url: string;
  updated_at: string;
}

export interface CampaignListPayload {
  campaigns: CampaignListItem[];
}

export interface FileEntry {
  path: string;
  name: string;
  section: string;
  title: string;
  size: number;
  updated_at: string;
}

export interface FileSectionCount {
  section: string;
  count: number;
}

export interface FileContent extends FileEntry {
  campaign_id: string;
  content: string;
}

export interface TableFile {
  path: string;
  name?: string;
  section?: string;
  title: string;
  content: string;
  size?: number;
  updated_at: string;
}

export interface TablePayload {
  index: TableFile | null;
  scene: TableFile | null;
  files: TableFile[];
}

export interface DmSurfaceScene {
  arc_id: string | null;
  scene_id: string;
  scene_type: string | null;
  path: string | null;
}

export interface DmSurfaceBeat {
  text: string;
  arc_id: string | null;
  scene_id: string | null;
  source_path: string;
}

export interface DmSurfacePayload {
  current_scene: DmSurfaceScene | null;
  beats: DmSurfaceBeat[];
  files: TableFile[];
}

export interface RuntimeTurnsSummary {
  count: number;
  latest_turn_id: number | null;
}

export interface RuntimeState {
  campaign?: string;
  status?: string;
  summary?: string;
  turn_counter?: number;
  mode_stack?: string[];
  pending_events?: unknown[];
  note_intake?: unknown[];
  next_speakers?: Array<string | Record<string, unknown>>;
  scene_closing_turns?: number | null;
  turns?: RuntimeTurnsSummary;
}

export interface CharacterRecord {
  campaign_id: string;
  character_id: string;
  player_id: string;
  name: string;
  archetype: string;
  species: string;
  culture: string;
  organization_role: string;
  pronouns: string;
  bio: string;
  goals: string[];
  attributes: Record<string, string>;
  skills: Record<string, string>;
  momentum: {
    current: number;
    floor: number;
    ceiling: number;
  };
  hp: {
    current: number;
    max: number;
  };
  inventory: string[];
  tags: string[];
  xp: number;
  level: number;
  skill_xp: Record<string, number>;
}

export interface TurnRecord {
  campaign_id: string;
  turn_id: number;
  session_id: string;
  scene_id: string | null;
  mode: string;
  speaker: string;
  role: string;
  character_id: string | null;
  source_path: string | null;
  prose: string;
  event_summaries: string[];
  events: unknown[];
  markdown: string;
  created_at: string;
  ts: string;
  arc_id: string | null;
  scene_type: string | null;
  turn_number_in_scene: number | null;
  visibility: string;
}

export interface MessageRecord {
  id: string;
  campaign_id: string;
  session_id: string;
  sender: string;
  recipient: string;
  type: string;
  body: string;
  created_at: string;
}

export interface ClockRecord {
  clock_id: string;
  scope: string;
  anchor_id: string | null;
  label: string;
  description: string;
  value: number;
  max: number;
  direction: string;
  visibility: string;
  status: string;
}

export interface SceneTrackerRecord {
  tracker_id: string;
  scene_id: string;
  label: string;
  value: number;
  max: number;
  resistance: number;
  impact_resistance: number;
  visibility: string;
  status: string;
}

export interface EventRecord {
  event_id: string;
  scene_id: string | null;
  turn_id: number | null;
  actor: string;
  event_type: string;
  visibility: string;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
  claimed_at: string | null;
}

export interface RollRecord {
  campaign_id?: string;
  roll_id: string;
  scene_id: string | null;
  session_id?: string;
  character_id: string;
  actor: string;
  skill: string;
  skill_modifier?: number;
  skill_tier?: string;
  attribute: string;
  attribute_modifier?: number;
  attribute_tier?: string;
  risk: string;
  dice: number[];
  total: number;
  target: number;
  target_id?: string | null;
  margin: number;
  metadata?: Record<string, unknown>;
  momentum_delta?: number;
  momentum_in?: number;
  momentum_out?: number;
  outcome: string;
  created_at: string;
}

export interface TarotRecord {
  id: string;
  actor: string;
  deck_name: string;
  card_name: string;
  influence: string;
  source_note: string;
  starts_turn: number;
  expires_turn: number;
  active: boolean;
}

export interface GraphEntity {
  id?: string;
  uid?: string;
  title?: string;
  type?: string;
  status?: string;
  prominence?: string;
  file_path?: string;
  tags?: string[];
}

export interface GraphEdge {
  type: string;
  source: string;
  source_title: string;
  target: string;
  target_title: string;
}

export interface GraphEntityType {
  type: string;
  count: number;
}

export interface GraphSnapshot {
  available: boolean;
  target: string;
  entities: GraphEntity[];
  edges: GraphEdge[];
  entity_types: GraphEntityType[];
  error?: string;
}

export interface LiveCursors {
  turn: number | null;
  messages: string | null;
  events: string | null;
  rolls: string | null;
}

export interface SummaryPayload {
  campaign_id: string;
  generated_at: string;
  runtime: RuntimeState | null;
  characters: CharacterRecord[];
  clocks: ClockRecord[];
  scene_trackers: SceneTrackerRecord[];
  tarot: TarotRecord[];
  graph: GraphSnapshot;
  dm_surface: DmSurfacePayload;
  database_error?: string;
}

export interface LivePayload {
  campaign_id: string;
  generated_at: string;
  turns: TurnRecord[];
  messages: MessageRecord[];
  events: EventRecord[];
  rolls: RollRecord[];
  cursors: LiveCursors;
  runtime?: RuntimeState | null;
  clocks?: ClockRecord[];
  scene_trackers?: SceneTrackerRecord[];
  tarot?: TarotRecord[];
  dm_surface?: DmSurfacePayload;
  database_error?: string;
}

export interface TableResourcePayload {
  campaign_id: string;
  generated_at: string;
  table: TablePayload;
}

export interface TurnRangePayload {
  campaign_id: string;
  from_turn: number;
  to_turn: number;
  items: TurnRecord[];
  database_error?: string;
}

export interface SceneIndexScene {
  scene_id: string | null;
  scene_type: string | null;
  mode: string | null;
  status: string | null;
  first_turn_id: number;
  last_turn_id: number;
  turn_count: number;
  summary_path: string | null;
}

export interface SceneIndexArc {
  arc_id: string | null;
  first_turn_id: number;
  last_turn_id: number;
  turn_count: number;
  summary_path: string | null;
  scenes: SceneIndexScene[];
}

export interface SceneIndexActive {
  arc_id: string | null;
  scene_id: string | null;
  scene_type: string | null;
}

export interface SceneIndexPayload {
  campaign_id: string;
  generated_at: string;
  arcs: SceneIndexArc[];
  active: SceneIndexActive | null;
  database_error?: string;
}

export interface FileListPayload {
  campaign_id: string;
  root: string;
  files: FileEntry[];
  sections?: FileSectionCount[];
}

export interface TurnOutputPayload {
  active: boolean;
  campaign_id: string;
  files: { stderr: string | null; stdout: string | null };
  generated_at: string;
  role: string | null;
  speaker: string | null;
  status: string;
  stderr: string;
  stderr_bytes: number;
  stderr_truncated: boolean;
  stdout: string;
  stdout_bytes: number;
  stdout_truncated: boolean;
  turn_dir: string | null;
  turn_id: number | null;
  turn_number: number | null;
  updated_at: string | null;
}
