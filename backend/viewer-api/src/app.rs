use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use axum::extract::{Path, Query, State};
use axum::routing::get;
use axum::{Json, Router};
use chrono::Utc;
use serde_json::{Value, json};
use sqlx::PgPool;

use crate::db;
use crate::error::{ApiError, ApiResult};
use crate::s3_store::{S3Store, file_matches_section, file_sections};
use crate::types::{FileContent, FileEntry};

#[derive(Clone)]
pub struct AppState {
    pub db: PgPool,
    pub store: S3Store,
}

impl AppState {
    pub async fn from_env() -> ApiResult<Self> {
        Ok(Self {
            db: db::connect_from_env().await?,
            store: S3Store::from_env().await,
        })
    }
}

pub fn routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/v1/health", get(health))
        .route("/v1/campaigns", get(campaigns))
        .route("/v1/campaigns/{campaign_id}/summary", get(summary))
        .route("/v1/campaigns/{campaign_id}/dashboard", get(dashboard))
        .route("/v1/campaigns/{campaign_id}/live", get(live))
        .route("/v1/campaigns/{campaign_id}/table", get(table))
        .route("/v1/campaigns/{campaign_id}/turns", get(turns))
        .route("/v1/campaigns/{campaign_id}/turns/range", get(turns_range))
        .route("/v1/campaigns/{campaign_id}/scenes", get(scenes))
        .route("/v1/campaigns/{campaign_id}/messages", get(messages))
        .route("/v1/campaigns/{campaign_id}/events", get(events))
        .route("/v1/campaigns/{campaign_id}/rolls", get(rolls))
        .route("/v1/campaigns/{campaign_id}/files", get(files))
        .route("/v1/campaigns/{campaign_id}/turn-output", get(turn_output))
        .route(
            "/v1/campaigns/{campaign_id}/current-turn-output",
            get(turn_output),
        )
}

async fn health(State(state): State<Arc<AppState>>) -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "agents-of-glass-viewer-api",
        "storage": if state.store.configured() { "s3" } else { "none" },
    }))
}

async fn campaigns(State(state): State<Arc<AppState>>) -> ApiResult<Json<Value>> {
    Ok(Json(
        json!({ "campaigns": db::campaigns(&state.db).await? }),
    ))
}

async fn summary(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    Ok(Json(summary_payload(&state, &campaign_id).await?))
}

async fn dashboard(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    let mut payload = summary_payload(&state, &campaign_id).await?;
    let table = table_payload(&state, &campaign_id).await?;
    let live = live_payload(&state, &campaign_id, &query).await?;
    merge_object(&mut payload, table);
    merge_object(&mut payload, live);
    Ok(Json(payload))
}

async fn live(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    Ok(Json(live_payload(&state, &campaign_id, &query).await?))
}

async fn table(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    Ok(Json(table_payload(&state, &campaign_id).await?))
}

async fn turns(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    let limit = query_i64(&query, "limit", 50, 1, 500)?;
    let after_turn = query_i32_opt(&query, "after_turn", 0, 1_000_000)?;
    let (items, cursor) = db::turn_delta(&state.db, &campaign_id, after_turn, limit).await?;
    Ok(Json(json!({
        "campaign_id": campaign_id,
        "items": items,
        "cursor": cursor,
    })))
}

async fn turns_range(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    let from_turn = query_i32_required(&query, "from_turn", 1, 1_000_000)?;
    let to_turn = query_i32_required(&query, "to_turn", 1, 1_000_000)?;
    if to_turn < from_turn {
        return Err(ApiError::BadRequest("to_turn must be >= from_turn".into()));
    }
    if to_turn - from_turn + 1 > 500 {
        return Err(ApiError::BadRequest(
            "turn range exceeds max span 500".into(),
        ));
    }
    let items = db::turn_range(&state.db, &campaign_id, from_turn, to_turn).await?;
    Ok(Json(json!({
        "campaign_id": campaign_id,
        "from_turn": from_turn,
        "to_turn": to_turn,
        "items": items,
    })))
}

async fn scenes(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    Ok(Json(scene_index_payload(&state, &campaign_id).await?))
}

async fn messages(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    let limit = query_i64(&query, "limit", 100, 1, 1000)?;
    let cursor = query.get("after").map(String::as_str);
    let (items, next_cursor) = db::message_delta(&state.db, &campaign_id, cursor, limit).await?;
    Ok(Json(json!({
        "campaign_id": campaign_id,
        "items": items,
        "cursor": next_cursor.or_else(|| cursor.map(str::to_string)),
    })))
}

async fn events(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    let limit = query_i64(&query, "limit", 100, 1, 1000)?;
    let cursor = query.get("after").map(String::as_str);
    let (items, next_cursor) = db::event_delta(&state.db, &campaign_id, cursor, limit).await?;
    Ok(Json(json!({
        "campaign_id": campaign_id,
        "items": items,
        "cursor": next_cursor.or_else(|| cursor.map(str::to_string)),
    })))
}

async fn rolls(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    let limit = query_i64(&query, "limit", 50, 1, 500)?;
    let cursor = query.get("after").map(String::as_str);
    let (items, next_cursor) = db::roll_delta(&state.db, &campaign_id, cursor, limit).await?;
    Ok(Json(json!({
        "campaign_id": campaign_id,
        "items": items,
        "cursor": next_cursor.or_else(|| cursor.map(str::to_string)),
    })))
}

async fn files(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
    Query(query): Query<HashMap<String, String>>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    if let Some(path) = query.get("path") {
        validate_relative_path(path)?;
        let index = state.store.file_index(&campaign_id).await?;
        if !index.files.iter().any(|entry| entry.path == *path) {
            return Err(ApiError::NotFound);
        }
        let content = state
            .store
            .file_content(&campaign_id, path)
            .await?
            .ok_or(ApiError::NotFound)?;
        return Ok(Json(json!(content)));
    }

    let mut files = state.store.file_index(&campaign_id).await?.files;
    if let Some(section) = query.get("section") {
        files.retain(|entry| file_matches_section(entry, section));
    } else if let Some(prefix) = query.get("prefix") {
        files.retain(|entry| entry.path.starts_with(prefix));
    } else if !query_bool(&query, "all", false) {
        let sections = file_sections(&files);
        return Ok(Json(json!({
            "campaign_id": campaign_id,
            "root": campaign_id,
            "sections": sections,
            "files": [],
        })));
    }
    let limit = query_i64(&query, "limit", 100, 1, 5000)? as usize;
    files.truncate(limit);
    Ok(Json(json!({
        "campaign_id": campaign_id,
        "root": campaign_id,
        "files": files,
    })))
}

async fn turn_output(
    State(state): State<Arc<AppState>>,
    Path(campaign_id): Path<String>,
) -> ApiResult<Json<Value>> {
    validate_campaign_id(&campaign_id)?;
    ensure_campaign(&state, &campaign_id).await?;
    Ok(Json(turn_output_payload(&state, &campaign_id).await?))
}

async fn summary_payload(state: &AppState, campaign_id: &str) -> ApiResult<Value> {
    let runtime = db::runtime_payload(&state.db, campaign_id).await?;
    let characters = db::characters(&state.db, campaign_id).await?;
    let clocks = db::clocks(&state.db, campaign_id).await?;
    let scene_trackers = db::scene_trackers(&state.db, campaign_id).await?;
    let tarot = db::tarot(&state.db, campaign_id).await?;
    let dm_surface = dm_surface_payload(state, campaign_id).await?;
    Ok(json!({
        "campaign_id": campaign_id,
        "generated_at": now_iso(),
        "runtime": runtime,
        "characters": characters,
        "clocks": clocks,
        "scene_trackers": scene_trackers,
        "tarot": tarot,
        "dm_surface": dm_surface,
    }))
}

async fn table_payload(state: &AppState, campaign_id: &str) -> ApiResult<Value> {
    Ok(json!({
        "campaign_id": campaign_id,
        "generated_at": now_iso(),
        "table": state.store.table(campaign_id).await?,
    }))
}

async fn live_payload(
    state: &AppState,
    campaign_id: &str,
    query: &HashMap<String, String>,
) -> ApiResult<Value> {
    let turn_limit = query_i64(query, "turns", 20, 1, 100)?;
    let message_limit = query_i64(query, "messages", 100, 1, 500)?;
    let event_limit = query_i64(query, "events", 100, 1, 500)?;
    let roll_limit = query_i64(query, "rolls", 50, 1, 250)?;
    let after_turn = query_i32_opt(query, "after_turn", 0, 1_000_000)?;
    let messages_after = query.get("messages_after").map(String::as_str);
    let events_after = query.get("events_after").map(String::as_str);
    let rolls_after = query.get("rolls_after").map(String::as_str);

    let (turns, turn_cursor) =
        db::turn_delta(&state.db, campaign_id, after_turn, turn_limit).await?;
    let (messages, messages_cursor) =
        db::message_delta(&state.db, campaign_id, messages_after, message_limit).await?;
    let (events, events_cursor) =
        db::event_delta(&state.db, campaign_id, events_after, event_limit).await?;
    let (rolls, rolls_cursor) =
        db::roll_delta(&state.db, campaign_id, rolls_after, roll_limit).await?;

    let mut payload = json!({
        "campaign_id": campaign_id,
        "generated_at": now_iso(),
        "turns": turns,
        "messages": messages,
        "events": events,
        "rolls": rolls,
        "cursors": {
            "turn": turn_cursor.or(after_turn),
            "messages": messages_cursor.or_else(|| messages_after.map(str::to_string)),
            "events": events_cursor.or_else(|| events_after.map(str::to_string)),
            "rolls": rolls_cursor.or_else(|| rolls_after.map(str::to_string)),
        },
    });

    if query_bool(query, "include_state", false) {
        let object = payload.as_object_mut().expect("payload is object");
        object.insert(
            "runtime".into(),
            db::runtime_payload(&state.db, campaign_id)
                .await?
                .unwrap_or(Value::Null),
        );
        object.insert(
            "clocks".into(),
            json!(db::clocks(&state.db, campaign_id).await?),
        );
        object.insert(
            "scene_trackers".into(),
            json!(db::scene_trackers(&state.db, campaign_id).await?),
        );
        object.insert(
            "tarot".into(),
            json!(db::tarot(&state.db, campaign_id).await?),
        );
        object.insert(
            "dm_surface".into(),
            dm_surface_payload(state, campaign_id).await?,
        );
    }

    Ok(payload)
}

async fn dm_surface_payload(state: &AppState, campaign_id: &str) -> ApiResult<Value> {
    let mut dm_surface = state.store.dm_surface(campaign_id).await?;
    if dm_surface.current_scene.is_none() {
        dm_surface.current_scene = db::latest_scene(&state.db, campaign_id).await?;
    }
    Ok(json!(dm_surface))
}

async fn scene_index_payload(state: &AppState, campaign_id: &str) -> ApiResult<Value> {
    let rows = db::scene_rows(&state.db, campaign_id).await?;
    let file_paths: HashSet<String> = state
        .store
        .published_file_paths(campaign_id)
        .await?
        .into_iter()
        .collect();
    let mut arcs: Vec<Value> = Vec::new();
    let mut arc_positions: HashMap<String, usize> = HashMap::new();

    for row in rows {
        let arc_id = row
            .get("arc_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let scene_id = row
            .get("scene_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let key = arc_id.clone().unwrap_or_default();
        let scene_entry = json!({
            "scene_id": scene_id,
            "scene_type": row.get("scene_type").cloned().unwrap_or(Value::Null),
            "mode": row.get("mode").cloned().unwrap_or(Value::Null),
            "status": row.get("scene_status").cloned().unwrap_or(Value::Null),
            "first_turn_id": row.get("first_turn_id").cloned().unwrap_or(Value::Null),
            "last_turn_id": row.get("last_turn_id").cloned().unwrap_or(Value::Null),
            "turn_count": row.get("turn_count").cloned().unwrap_or(Value::Null),
            "summary_path": scene_summary_path(&file_paths, arc_id.as_deref(), scene_id.as_deref()),
        });
        let pos = if let Some(pos) = arc_positions.get(&key) {
            *pos
        } else {
            let pos = arcs.len();
            arc_positions.insert(key, pos);
            arcs.push(json!({
                "arc_id": arc_id,
                "first_turn_id": row.get("first_turn_id").cloned().unwrap_or(Value::Null),
                "last_turn_id": row.get("last_turn_id").cloned().unwrap_or(Value::Null),
                "turn_count": 0,
                "summary_path": arc_summary_path(&file_paths, row.get("arc_id").and_then(Value::as_str)),
                "scenes": [],
            }));
            pos
        };
        let arc = arcs[pos].as_object_mut().expect("arc is object");
        arc.insert(
            "last_turn_id".into(),
            row.get("last_turn_id").cloned().unwrap_or(Value::Null),
        );
        let current_count = arc
            .get("turn_count")
            .and_then(Value::as_i64)
            .unwrap_or_default();
        let row_count = row
            .get("turn_count")
            .and_then(Value::as_i64)
            .unwrap_or_default();
        arc.insert("turn_count".into(), json!(current_count + row_count));
        arc.get_mut("scenes")
            .and_then(Value::as_array_mut)
            .expect("scenes is array")
            .push(scene_entry);
    }

    let dm_surface = state.store.dm_surface(campaign_id).await?;
    let active = dm_surface
        .current_scene
        .or(db::latest_scene(&state.db, campaign_id).await?);

    Ok(json!({
        "campaign_id": campaign_id,
        "generated_at": now_iso(),
        "arcs": arcs,
        "active": active,
    }))
}

async fn turn_output_payload(state: &AppState, campaign_id: &str) -> ApiResult<Value> {
    let runtime = db::runtime_payload(&state.db, campaign_id).await?;
    let Some(runtime) = runtime else {
        return Ok(empty_turn_output(campaign_id));
    };
    let status = runtime
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or_default();
    if status != "running" {
        let mut payload = empty_turn_output(campaign_id);
        payload["status"] = json!(status);
        return Ok(payload);
    }

    let turn_number = runtime
        .pointer("/active_turn/turn_number")
        .and_then(Value::as_i64)
        .or_else(|| {
            runtime
                .get("turn_counter")
                .and_then(Value::as_i64)
                .map(|value| value + 1)
        })
        .unwrap_or_default();
    if turn_number <= 0 {
        let mut payload = empty_turn_output(campaign_id);
        payload["status"] = json!(status);
        return Ok(payload);
    }

    let turn_name = format!("{turn_number:04}");
    let candidates = turn_output_candidates(
        &state.store.file_index(campaign_id).await?.files,
        &turn_name,
    );
    let selected = candidates.into_iter().max_by_key(|candidate| {
        candidate
            .stdout
            .as_ref()
            .map(|entry| entry.updated_at.as_str())
            .max(
                candidate
                    .stderr
                    .as_ref()
                    .map(|entry| entry.updated_at.as_str()),
            )
            .unwrap_or_default()
            .to_string()
    });

    let mut payload = json!({
        "active": true,
        "campaign_id": campaign_id,
        "generated_at": now_iso(),
        "status": status,
        "turn_id": runtime
            .pointer("/active_turn/turn_id")
            .and_then(Value::as_str)
            .map(str::to_string)
            .unwrap_or_else(|| format!("{campaign_id}-t{turn_number:04}")),
        "turn_number": turn_number,
        "speaker": null,
        "role": null,
        "turn_dir": null,
        "stdout": "",
        "stderr": "",
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "stdout_truncated": false,
        "stderr_truncated": false,
        "updated_at": null,
        "files": {
            "stdout": null,
            "stderr": null,
        },
    });

    let Some(selected) = selected else {
        return Ok(payload);
    };

    let stdout = file_content_for_entry(state, campaign_id, selected.stdout.as_ref()).await?;
    let stderr = file_content_for_entry(state, campaign_id, selected.stderr.as_ref()).await?;
    payload["speaker"] = json!(selected.speaker);
    payload["role"] = json!(selected.role);
    payload["turn_dir"] = json!(selected.turn_dir);
    payload["stdout"] = json!(
        stdout
            .as_ref()
            .map_or("", |content| content.content.as_str())
    );
    payload["stderr"] = json!(
        stderr
            .as_ref()
            .map_or("", |content| content.content.as_str())
    );
    payload["stdout_bytes"] = json!(file_size(stdout.as_ref(), selected.stdout.as_ref()));
    payload["stderr_bytes"] = json!(file_size(stderr.as_ref(), selected.stderr.as_ref()));
    payload["stdout_truncated"] = json!(is_truncated(stdout.as_ref()));
    payload["stderr_truncated"] = json!(is_truncated(stderr.as_ref()));
    payload["updated_at"] = json!(latest_updated_at([
        stdout.as_ref().map(|content| content.updated_at.as_str()),
        stderr.as_ref().map(|content| content.updated_at.as_str()),
        selected
            .stdout
            .as_ref()
            .map(|entry| entry.updated_at.as_str()),
        selected
            .stderr
            .as_ref()
            .map(|entry| entry.updated_at.as_str()),
    ]));
    payload["files"] = json!({
        "stdout": selected.stdout.map(|entry| entry.path),
        "stderr": selected.stderr.map(|entry| entry.path),
    });
    Ok(payload)
}

async fn ensure_campaign(state: &AppState, campaign_id: &str) -> ApiResult<()> {
    if db::campaign_exists(&state.db, campaign_id).await? {
        Ok(())
    } else {
        Err(ApiError::NotFound)
    }
}

fn validate_campaign_id(campaign_id: &str) -> ApiResult<()> {
    if campaign_id.is_empty()
        || campaign_id == "."
        || campaign_id == ".."
        || campaign_id.starts_with('.')
        || campaign_id.contains('/')
        || campaign_id.contains('\\')
    {
        return Err(ApiError::BadRequest("invalid campaign id".into()));
    }
    Ok(())
}

fn validate_relative_path(path: &str) -> ApiResult<()> {
    if path.is_empty()
        || path.starts_with('/')
        || path.starts_with('\\')
        || path
            .split('/')
            .any(|part| part == ".." || part.starts_with('.'))
    {
        return Err(ApiError::BadRequest("invalid campaign file path".into()));
    }
    Ok(())
}

fn query_i64(
    query: &HashMap<String, String>,
    name: &str,
    default: i64,
    min: i64,
    max: i64,
) -> ApiResult<i64> {
    let Some(raw) = query.get(name) else {
        return Ok(default);
    };
    let value = raw
        .parse::<i64>()
        .map_err(|_| ApiError::BadRequest(format!("{name} must be an integer")))?;
    if value < min || value > max {
        return Err(ApiError::BadRequest(format!(
            "{name} must be between {min} and {max}"
        )));
    }
    Ok(value)
}

fn query_i32_opt(
    query: &HashMap<String, String>,
    name: &str,
    min: i32,
    max: i32,
) -> ApiResult<Option<i32>> {
    query
        .get(name)
        .map(|_| query_i32_required(query, name, min, max))
        .transpose()
}

fn query_i32_required(
    query: &HashMap<String, String>,
    name: &str,
    min: i32,
    max: i32,
) -> ApiResult<i32> {
    let raw = query
        .get(name)
        .ok_or_else(|| ApiError::BadRequest(format!("{name} is required")))?;
    let value = raw
        .parse::<i32>()
        .map_err(|_| ApiError::BadRequest(format!("{name} must be an integer")))?;
    if value < min || value > max {
        return Err(ApiError::BadRequest(format!(
            "{name} must be between {min} and {max}"
        )));
    }
    Ok(value)
}

fn query_bool(query: &HashMap<String, String>, name: &str, default: bool) -> bool {
    query.get(name).map_or(default, |value| {
        matches!(value.as_str(), "1" | "true" | "yes" | "on")
    })
}

fn merge_object(target: &mut Value, source: Value) {
    if let (Some(target), Some(source)) = (target.as_object_mut(), source.as_object()) {
        for (key, value) in source {
            target.insert(key.clone(), value.clone());
        }
    }
}

fn arc_summary_path(paths: &HashSet<String>, arc_id: Option<&str>) -> Option<String> {
    let arc_id = arc_id?;
    let path = format!("arcs/{arc_id}/summary.md");
    paths.contains(&path).then_some(path)
}

fn scene_summary_path(
    paths: &HashSet<String>,
    arc_id: Option<&str>,
    scene_id: Option<&str>,
) -> Option<String> {
    let path = format!("arcs/{}/scenes/{}/summary.md", arc_id?, scene_id?);
    paths.contains(&path).then_some(path)
}

#[derive(Clone)]
struct TurnOutputCandidate {
    turn_dir: String,
    speaker: String,
    role: String,
    stdout: Option<FileEntry>,
    stderr: Option<FileEntry>,
}

fn turn_output_candidates(files: &[FileEntry], turn_name: &str) -> Vec<TurnOutputCandidate> {
    let mut candidates: HashMap<String, TurnOutputCandidate> = HashMap::new();
    for entry in files {
        let Some((turn_dir, kind)) = turn_output_part(&entry.path, turn_name) else {
            continue;
        };
        let (speaker, role) = turn_actor(&turn_dir);
        let candidate = candidates
            .entry(turn_dir.clone())
            .or_insert_with(|| TurnOutputCandidate {
                turn_dir,
                speaker,
                role,
                stdout: None,
                stderr: None,
            });
        match kind {
            "stdout" => candidate.stdout = Some(entry.clone()),
            "stderr" => candidate.stderr = Some(entry.clone()),
            _ => {}
        }
    }
    candidates.into_values().collect()
}

fn turn_output_part(path: &str, turn_name: &str) -> Option<(String, &'static str)> {
    for (file_name, kind) in [
        ("agent-stdout.txt", "stdout"),
        ("agent-stderr.txt", "stderr"),
    ] {
        let suffix = format!("/turns/{turn_name}/{file_name}");
        if path.ends_with(&suffix) {
            return Some((path.trim_end_matches(&format!("/{file_name}")).into(), kind));
        }
    }
    None
}

fn turn_actor(turn_dir: &str) -> (String, String) {
    if turn_dir.starts_with("dm/turns/") {
        return ("dm".into(), "dm".into());
    }
    let parts: Vec<&str> = turn_dir.split('/').collect();
    if parts.len() >= 4 && parts[0] == "players" && parts[2] == "turns" {
        return (parts[1].into(), "player".into());
    }
    ("unknown".into(), "unknown".into())
}

async fn file_content_for_entry(
    state: &AppState,
    campaign_id: &str,
    entry: Option<&FileEntry>,
) -> ApiResult<Option<FileContent>> {
    let Some(entry) = entry else {
        return Ok(None);
    };
    state.store.file_content(campaign_id, &entry.path).await
}

fn file_size(content: Option<&FileContent>, entry: Option<&FileEntry>) -> i64 {
    content
        .map(|content| content.size)
        .or_else(|| entry.map(|entry| entry.size))
        .unwrap_or_default()
}

fn is_truncated(content: Option<&FileContent>) -> bool {
    content.is_some_and(|content| content.size > content.content.len() as i64)
}

fn latest_updated_at<'a>(values: impl IntoIterator<Item = Option<&'a str>>) -> Option<&'a str> {
    values.into_iter().flatten().max()
}

fn empty_turn_output(campaign_id: &str) -> Value {
    json!({
        "active": false,
        "campaign_id": campaign_id,
        "generated_at": now_iso(),
        "status": null,
        "turn_id": null,
        "turn_number": null,
        "speaker": null,
        "role": null,
        "turn_dir": null,
        "stdout": "",
        "stderr": "",
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "stdout_truncated": false,
        "stderr_truncated": false,
        "updated_at": null,
        "files": {
            "stdout": null,
            "stderr": null,
        },
    })
}

fn now_iso() -> String {
    Utc::now().to_rfc3339()
}
