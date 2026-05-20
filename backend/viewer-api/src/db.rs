use chrono::{DateTime, Utc};
use serde_json::{Value, json};
use sqlx::postgres::{PgConnectOptions, PgPoolOptions, PgSslMode};
use sqlx::{PgPool, Row};
use std::env;
use uuid::Uuid;

use crate::error::{ApiError, ApiResult};

const CURSOR_SEPARATOR: &str = "::";

pub async fn connect_from_env() -> ApiResult<PgPool> {
    if let Ok(url) = env::var("DATABASE_URL") {
        return PgPoolOptions::new()
            .max_connections(env_u32("DB_MAX_CONNECTIONS", 5))
            .connect(&url)
            .await
            .map_err(ApiError::Db);
    }

    let host = env::var("DB_HOST")
        .or_else(|_| env::var("PGHOST"))
        .map_err(|_| ApiError::Config("DB_HOST or DATABASE_URL is required".into()))?;
    let port = env::var("DB_PORT")
        .or_else(|_| env::var("PGPORT"))
        .ok()
        .and_then(|v| v.parse::<u16>().ok())
        .unwrap_or(5432);
    let database = env::var("DB_NAME")
        .or_else(|_| env::var("PGDATABASE"))
        .map_err(|_| ApiError::Config("DB_NAME or PGDATABASE is required".into()))?;
    let username = env::var("DB_USERNAME")
        .or_else(|_| env::var("PGUSER"))
        .map_err(|_| ApiError::Config("DB_USERNAME or PGUSER is required".into()))?;
    let password = env::var("DB_PASSWORD")
        .or_else(|_| env::var("AOG_PG_PASSWORD"))
        .or_else(|_| env::var("PGPASSWORD"))
        .unwrap_or_default();
    let ssl_mode = match env::var("DB_SSLMODE")
        .unwrap_or_else(|_| "prefer".into())
        .as_str()
    {
        "disable" => PgSslMode::Disable,
        "require" => PgSslMode::Require,
        _ => PgSslMode::Prefer,
    };

    let mut options = PgConnectOptions::new()
        .host(&host)
        .port(port)
        .database(&database)
        .username(&username)
        .ssl_mode(ssl_mode);
    if !password.is_empty() {
        options = options.password(&password);
    }

    PgPoolOptions::new()
        .max_connections(env_u32("DB_MAX_CONNECTIONS", 5))
        .connect_with(options)
        .await
        .map_err(ApiError::Db)
}

fn env_u32(name: &str, default: u32) -> u32 {
    env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

fn iso(value: Option<DateTime<Utc>>) -> Value {
    value
        .map(|dt| json!(dt.to_rfc3339()))
        .unwrap_or(Value::Null)
}

fn array_or_empty(value: Option<Value>) -> Value {
    match value {
        Some(Value::Array(_)) => value.unwrap(),
        _ => json!([]),
    }
}

fn object_or_empty(value: Option<Value>) -> Value {
    match value {
        Some(Value::Object(_)) => value.unwrap(),
        _ => json!({}),
    }
}

fn cursor_from_parts(created_at: Option<DateTime<Utc>>, id: String) -> Option<String> {
    created_at.map(|dt| format!("{}{}{}", dt.to_rfc3339(), CURSOR_SEPARATOR, id))
}

fn parse_cursor(cursor: &str) -> ApiResult<(DateTime<Utc>, String)> {
    let (created, id) = cursor
        .split_once(CURSOR_SEPARATOR)
        .ok_or_else(|| ApiError::BadRequest("invalid cursor".into()))?;
    let dt = DateTime::parse_from_rfc3339(created)
        .map_err(|_| ApiError::BadRequest("invalid cursor timestamp".into()))?
        .with_timezone(&Utc);
    if id.is_empty() {
        return Err(ApiError::BadRequest("invalid cursor id".into()));
    }
    Ok((dt, id.to_string()))
}

pub async fn campaigns(pool: &PgPool) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(
        r#"
        WITH campaign_ids AS (
            SELECT campaign_id FROM campaign_runtime_states
            UNION SELECT campaign_id FROM turns
            UNION SELECT campaign_id FROM messages
            UNION SELECT campaign_id FROM events
            UNION SELECT campaign_id FROM rolls
            UNION SELECT campaign_id FROM characters
            UNION SELECT campaign_id FROM clocks
        ),
        turn_updates AS (
            SELECT campaign_id, max(created_at) AS updated_at
            FROM turns
            GROUP BY campaign_id
        )
        SELECT c.campaign_id,
               COALESCE(r.updated_at, t.updated_at, now()) AS updated_at
        FROM campaign_ids c
        LEFT JOIN campaign_runtime_states r ON r.campaign_id = c.campaign_id
        LEFT JOIN turn_updates t ON t.campaign_id = c.campaign_id
        ORDER BY c.campaign_id
        "#,
    )
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|row| {
            let campaign_id: String = row.get("campaign_id");
            let updated_at: Option<DateTime<Utc>> = row.try_get("updated_at").ok();
            json!({
                "campaign_id": campaign_id,
                "dashboard_url": format!("/v1/campaigns/{campaign_id}/dashboard"),
                "files_url": format!("/v1/campaigns/{campaign_id}/files"),
                "updated_at": iso(updated_at),
            })
        })
        .collect())
}

pub async fn campaign_exists(pool: &PgPool, campaign_id: &str) -> ApiResult<bool> {
    let row = sqlx::query(
        r#"
        SELECT EXISTS (
            SELECT 1 FROM campaign_runtime_states WHERE campaign_id = $1
            UNION SELECT 1 FROM turns WHERE campaign_id = $1
            UNION SELECT 1 FROM messages WHERE campaign_id = $1
            UNION SELECT 1 FROM events WHERE campaign_id = $1
            UNION SELECT 1 FROM rolls WHERE campaign_id = $1
            UNION SELECT 1 FROM characters WHERE campaign_id = $1
            UNION SELECT 1 FROM clocks WHERE campaign_id = $1
        ) AS found
        "#,
    )
    .bind(campaign_id)
    .fetch_one(pool)
    .await?;
    Ok(row.get("found"))
}

pub async fn runtime_payload(pool: &PgPool, campaign_id: &str) -> ApiResult<Option<Value>> {
    let row = sqlx::query(
        r#"
        SELECT campaign_id, status, created_at, updated_at, wrapped_at, summary,
               turn_counter, mode_stack, pending_events, note_intake,
               next_speakers, scene_closing_turns,
               active_turn_id, active_turn_number, active_turn_actor,
               active_turn_role, active_turn_mode, active_turn_scene_id,
               active_turn_kind, closeout_valid, closeout_problems
        FROM campaign_runtime_states
        WHERE campaign_id = $1
        "#,
    )
    .bind(campaign_id)
    .fetch_optional(pool)
    .await?;
    let Some(row) = row else {
        return Ok(None);
    };

    let turn_row = sqlx::query("SELECT count(*) AS count, max(turn_id) AS latest_turn_id FROM turns WHERE campaign_id = $1")
        .bind(campaign_id)
        .fetch_one(pool)
        .await?;
    let turn_count: i64 = turn_row.get("count");
    let latest_turn_id: Option<i32> = turn_row.get("latest_turn_id");
    let turn_counter: i32 = row.get("turn_counter");
    let active_turn_id: Option<String> = row.get("active_turn_id");
    let active_turn = active_turn_id.as_ref().map(|turn_id| {
        json!({
            "turn_id": turn_id,
            "turn_number": row.get::<Option<i32>, _>("active_turn_number"),
            "actor": row.get::<Option<String>, _>("active_turn_actor"),
            "role": row.get::<Option<String>, _>("active_turn_role"),
            "mode": row.get::<Option<String>, _>("active_turn_mode"),
            "scene_id": row.get::<Option<String>, _>("active_turn_scene_id"),
            "kind": row.get::<Option<String>, _>("active_turn_kind"),
            "closeout_valid": row.get::<Option<bool>, _>("closeout_valid"),
            "closeout_problems": array_or_empty(row.try_get("closeout_problems").ok()),
        })
    });

    Ok(Some(json!({
        "schema_version": 5,
        "campaign": row.get::<String, _>("campaign_id"),
        "status": row.get::<String, _>("status"),
        "created_at": iso(row.try_get("created_at").ok()),
        "updated_at": iso(row.try_get("updated_at").ok()),
        "wrapped_at": iso(row.try_get("wrapped_at").ok()),
        "summary": row.get::<String, _>("summary"),
        "turn_counter": i32::max(turn_counter, latest_turn_id.unwrap_or(0)),
        "mode_stack": array_or_empty(row.try_get("mode_stack").ok()),
        "pending_events": array_or_empty(row.try_get("pending_events").ok()),
        "note_intake": array_or_empty(row.try_get("note_intake").ok()),
        "next_speakers": array_or_empty(row.try_get("next_speakers").ok()),
        "scene_closing_turns": row.get::<Option<i32>, _>("scene_closing_turns"),
        "active_turn": active_turn,
        "turns": {
            "count": turn_count,
            "latest_turn_id": latest_turn_id,
        },
    })))
}

pub async fn characters(pool: &PgPool, campaign_id: &str) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(
        r#"
        SELECT campaign_id, character_id, player_id, name, archetype, species,
               culture, organization_role, pronouns, bio, goals, primary_drive,
               positive_trait, table_presence, non_work_want, opening_social_action,
               life_prompt_answers, pull_utilization_note, attributes, skills,
               momentum_current, momentum_floor, momentum_ceiling,
               hp_current, hp_max, inventory, tags, xp, level, skill_xp,
               skill_meta, created_at, updated_at
        FROM characters
        WHERE campaign_id = $1
        ORDER BY character_id
        "#,
    )
    .bind(campaign_id)
    .fetch_all(pool)
    .await?;
    Ok(rows.into_iter().map(character_json).collect())
}

fn character_json(row: sqlx::postgres::PgRow) -> Value {
    json!({
        "campaign_id": row.get::<String, _>("campaign_id"),
        "character_id": row.get::<String, _>("character_id"),
        "player_id": row.get::<String, _>("player_id"),
        "name": row.get::<String, _>("name"),
        "archetype": row.get::<String, _>("archetype"),
        "species": row.get::<String, _>("species"),
        "culture": row.get::<String, _>("culture"),
        "organization_role": row.get::<String, _>("organization_role"),
        "pronouns": row.get::<String, _>("pronouns"),
        "bio": row.get::<String, _>("bio"),
        "goals": array_or_empty(row.try_get("goals").ok()),
        "primary_drive": row.get::<String, _>("primary_drive"),
        "positive_trait": row.get::<String, _>("positive_trait"),
        "table_presence": row.get::<String, _>("table_presence"),
        "non_work_want": row.get::<String, _>("non_work_want"),
        "opening_social_action": row.get::<String, _>("opening_social_action"),
        "life_prompt_answers": array_or_empty(row.try_get("life_prompt_answers").ok()),
        "pull_utilization_note": row.get::<String, _>("pull_utilization_note"),
        "attributes": object_or_empty(row.try_get("attributes").ok()),
        "skills": object_or_empty(row.try_get("skills").ok()),
        "momentum": {
            "current": row.get::<i32, _>("momentum_current"),
            "floor": row.get::<i32, _>("momentum_floor"),
            "ceiling": row.get::<i32, _>("momentum_ceiling"),
        },
        "hp": {
            "current": row.get::<i32, _>("hp_current"),
            "max": row.get::<i32, _>("hp_max"),
        },
        "inventory": array_or_empty(row.try_get("inventory").ok()),
        "tags": row.get::<Vec<String>, _>("tags"),
        "xp": row.get::<i32, _>("xp"),
        "level": row.get::<i32, _>("level"),
        "skill_xp": object_or_empty(row.try_get("skill_xp").ok()),
        "skill_meta": object_or_empty(row.try_get("skill_meta").ok()),
        "created_at": iso(row.try_get("created_at").ok()),
        "updated_at": iso(row.try_get("updated_at").ok()),
    })
}

pub async fn clocks(pool: &PgPool, campaign_id: &str) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(
        r#"
        SELECT campaign_id, clock_id, scope, anchor_id, label, description,
               value, max_value, direction, visibility, status, created_by,
               updated_by, created_at, updated_at, resolved_at, resolution_note
        FROM clocks
        WHERE campaign_id = $1
        ORDER BY scope, anchor_id NULLS FIRST, clock_id
        "#,
    )
    .bind(campaign_id)
    .fetch_all(pool)
    .await?;
    Ok(rows.into_iter().map(clock_json).collect())
}

fn clock_json(row: sqlx::postgres::PgRow) -> Value {
    json!({
        "campaign_id": row.get::<String, _>("campaign_id"),
        "clock_id": row.get::<String, _>("clock_id"),
        "scope": row.get::<String, _>("scope"),
        "anchor_id": row.get::<Option<String>, _>("anchor_id"),
        "label": row.get::<String, _>("label"),
        "description": row.get::<String, _>("description"),
        "value": row.get::<i32, _>("value"),
        "max": row.get::<i32, _>("max_value"),
        "direction": row.get::<String, _>("direction"),
        "visibility": row.get::<String, _>("visibility"),
        "status": row.get::<String, _>("status"),
        "created_by": row.get::<String, _>("created_by"),
        "updated_by": row.get::<String, _>("updated_by"),
        "created_at": iso(row.try_get("created_at").ok()),
        "updated_at": iso(row.try_get("updated_at").ok()),
        "resolved_at": iso(row.try_get("resolved_at").ok()),
        "resolution_note": row.get::<Option<String>, _>("resolution_note"),
    })
}

pub async fn scene_trackers(pool: &PgPool, campaign_id: &str) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(
        r#"
        SELECT campaign_id, tracker_id, scene_id, label, value, max_value,
               resistance, impact_resistance, visibility, status, updated_by,
               created_at, updated_at
        FROM scene_trackers
        WHERE campaign_id = $1
        ORDER BY scene_id, tracker_id
        "#,
    )
    .bind(campaign_id)
    .fetch_all(pool)
    .await?;
    Ok(rows.into_iter().map(scene_tracker_json).collect())
}

fn scene_tracker_json(row: sqlx::postgres::PgRow) -> Value {
    let visibility: String = row.get("visibility");
    json!({
        "campaign_id": row.get::<String, _>("campaign_id"),
        "tracker_id": row.get::<String, _>("tracker_id"),
        "scene_id": row.get::<String, _>("scene_id"),
        "label": row.get::<String, _>("label"),
        "value": row.get::<i32, _>("value"),
        "max": row.get::<i32, _>("max_value"),
        "resistance": row.get::<i32, _>("resistance"),
        "impact_resistance": row.get::<i32, _>("impact_resistance"),
        "public": visibility == "public",
        "visibility": visibility,
        "status": row.get::<String, _>("status"),
        "updated_by": row.get::<String, _>("updated_by"),
        "created_at": iso(row.try_get("created_at").ok()),
        "updated_at": iso(row.try_get("updated_at").ok()),
    })
}

pub async fn tarot(pool: &PgPool, campaign_id: &str) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(
        r#"
        SELECT id, campaign_id, actor, deck_id, deck_name, card_id, card_name,
               influence, source_note, starts_turn, expires_turn, active, created_at
        FROM tarot_influences
        WHERE campaign_id = $1
        ORDER BY starts_turn DESC, created_at DESC
        LIMIT 100
        "#,
    )
    .bind(campaign_id)
    .fetch_all(pool)
    .await?;
    Ok(rows.into_iter().map(tarot_json).collect())
}

fn tarot_json(row: sqlx::postgres::PgRow) -> Value {
    json!({
        "id": row.get::<Uuid, _>("id").to_string(),
        "campaign_id": row.get::<String, _>("campaign_id"),
        "actor": row.get::<String, _>("actor"),
        "deck_id": row.get::<String, _>("deck_id"),
        "deck_name": row.get::<String, _>("deck_name"),
        "card_id": row.get::<String, _>("card_id"),
        "card_name": row.get::<String, _>("card_name"),
        "influence": row.get::<String, _>("influence"),
        "source_note": row.get::<String, _>("source_note"),
        "starts_turn": row.get::<i32, _>("starts_turn"),
        "expires_turn": row.get::<i32, _>("expires_turn"),
        "active": row.get::<bool, _>("active"),
        "created_at": iso(row.try_get("created_at").ok()),
    })
}

pub async fn turn_delta(
    pool: &PgPool,
    campaign_id: &str,
    after_turn: Option<i32>,
    limit: i64,
) -> ApiResult<(Vec<Value>, Option<i32>)> {
    let rows = if let Some(after) = after_turn {
        sqlx::query(turn_select_after_sql())
            .bind(campaign_id)
            .bind(after)
            .bind(limit)
            .fetch_all(pool)
            .await?
    } else {
        let mut rows = sqlx::query(turn_select_latest_sql())
            .bind(campaign_id)
            .bind(limit)
            .fetch_all(pool)
            .await?;
        rows.reverse();
        rows
    };
    let cursor = rows
        .last()
        .map(|row| row.get::<i32, _>("turn_id"))
        .or(after_turn);
    Ok((rows.into_iter().map(turn_json).collect(), cursor))
}

pub async fn turn_range(
    pool: &PgPool,
    campaign_id: &str,
    from_turn: i32,
    to_turn: i32,
) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(turn_range_sql())
        .bind(campaign_id)
        .bind(from_turn)
        .bind(to_turn)
        .bind(i64::from(to_turn - from_turn + 1))
        .fetch_all(pool)
        .await?;
    Ok(rows.into_iter().map(turn_json).collect())
}

fn turn_select_after_sql() -> &'static str {
    r#"
        SELECT campaign_id, turn_id, session_id, scene_id, mode, speaker, role,
               character_id, source_path, prose, event_summaries, events, markdown,
               created_at, arc_id, scene_type, turn_number_in_scene, visibility,
               turn_summary, next_speaker, scene_status, state_changes, rolls,
               turn_type, open_questions, position, pressure, turn_end
        FROM turns
        WHERE campaign_id = $1 AND turn_id > $2
        ORDER BY turn_id ASC
        LIMIT $3
    "#
}

fn turn_select_latest_sql() -> &'static str {
    r#"
        SELECT campaign_id, turn_id, session_id, scene_id, mode, speaker, role,
               character_id, source_path, prose, event_summaries, events, markdown,
               created_at, arc_id, scene_type, turn_number_in_scene, visibility,
               turn_summary, next_speaker, scene_status, state_changes, rolls,
               turn_type, open_questions, position, pressure, turn_end
        FROM turns
        WHERE campaign_id = $1
        ORDER BY turn_id DESC
        LIMIT $2
    "#
}

fn turn_range_sql() -> &'static str {
    r#"
    SELECT campaign_id, turn_id, session_id, scene_id, mode, speaker, role,
           character_id, source_path, prose, event_summaries, events, markdown,
           created_at, arc_id, scene_type, turn_number_in_scene, visibility,
           turn_summary, next_speaker, scene_status, state_changes, rolls,
           turn_type, open_questions, position, pressure, turn_end
    FROM turns
    WHERE campaign_id = $1 AND turn_id >= $2 AND turn_id <= $3
    ORDER BY turn_id ASC
    LIMIT $4
    "#
}

fn turn_json(row: sqlx::postgres::PgRow) -> Value {
    json!({
        "campaign_id": row.get::<String, _>("campaign_id"),
        "turn_id": row.get::<i32, _>("turn_id"),
        "session_id": row.get::<String, _>("session_id"),
        "scene_id": row.get::<Option<String>, _>("scene_id"),
        "mode": row.get::<String, _>("mode"),
        "speaker": row.get::<String, _>("speaker"),
        "role": row.get::<String, _>("role"),
        "character_id": row.get::<Option<String>, _>("character_id"),
        "source_path": row.get::<Option<String>, _>("source_path"),
        "prose": row.get::<String, _>("prose"),
        "event_summaries": array_or_empty(row.try_get("event_summaries").ok()),
        "events": array_or_empty(row.try_get("events").ok()),
        "markdown": row.get::<String, _>("markdown"),
        "created_at": iso(row.try_get("created_at").ok()),
        "ts": iso(row.try_get("created_at").ok()),
        "arc_id": row.get::<Option<String>, _>("arc_id"),
        "scene_type": row.get::<Option<String>, _>("scene_type"),
        "turn_number_in_scene": row.get::<Option<i32>, _>("turn_number_in_scene"),
        "visibility": row.get::<String, _>("visibility"),
        "turn_summary": row.get::<String, _>("turn_summary"),
        "next_speaker": row.get::<String, _>("next_speaker"),
        "scene_status": row.get::<String, _>("scene_status"),
        "state_changes": array_or_empty(row.try_get("state_changes").ok()),
        "rolls": row.get::<String, _>("rolls"),
        "turn_type": row.get::<Option<String>, _>("turn_type"),
        "open_questions": array_or_empty(row.try_get("open_questions").ok()),
        "position": row.get::<String, _>("position"),
        "pressure": row.get::<String, _>("pressure"),
        "turn_end": object_or_empty(row.try_get("turn_end").ok()),
    })
}

pub async fn message_delta(
    pool: &PgPool,
    campaign_id: &str,
    cursor: Option<&str>,
    limit: i64,
) -> ApiResult<(Vec<Value>, Option<String>)> {
    let rows = if let Some(cursor) = cursor {
        let (created_at, id) = parse_cursor(cursor)?;
        sqlx::query(message_delta_sql(true))
            .bind(campaign_id)
            .bind(created_at)
            .bind(
                Uuid::parse_str(&id)
                    .map_err(|_| ApiError::BadRequest("invalid message cursor".into()))?,
            )
            .bind(limit)
            .fetch_all(pool)
            .await?
    } else {
        let mut rows = sqlx::query(message_delta_sql(false))
            .bind(campaign_id)
            .bind(limit)
            .fetch_all(pool)
            .await?;
        rows.reverse();
        rows
    };
    let next_cursor = rows
        .last()
        .and_then(|row| {
            cursor_from_parts(
                row.try_get("created_at").ok(),
                row.get::<Uuid, _>("id").to_string(),
            )
        })
        .or_else(|| cursor.map(str::to_string));
    Ok((rows.into_iter().map(message_json).collect(), next_cursor))
}

fn message_delta_sql(with_cursor: bool) -> &'static str {
    if with_cursor {
        r#"
        SELECT id, campaign_id, session_id, sender, recipient, type, body, created_at
        FROM messages
        WHERE campaign_id = $1 AND (created_at, id) > ($2, $3)
        ORDER BY created_at ASC, id ASC
        LIMIT $4
        "#
    } else {
        r#"
        SELECT id, campaign_id, session_id, sender, recipient, type, body, created_at
        FROM messages
        WHERE campaign_id = $1
        ORDER BY created_at DESC, id DESC
        LIMIT $2
        "#
    }
}

fn message_json(row: sqlx::postgres::PgRow) -> Value {
    json!({
        "id": row.get::<Uuid, _>("id").to_string(),
        "campaign_id": row.get::<String, _>("campaign_id"),
        "session_id": row.get::<String, _>("session_id"),
        "sender": row.get::<String, _>("sender"),
        "recipient": row.get::<String, _>("recipient"),
        "type": row.get::<String, _>("type"),
        "body": row.get::<String, _>("body"),
        "created_at": iso(row.try_get("created_at").ok()),
    })
}

pub async fn event_delta(
    pool: &PgPool,
    campaign_id: &str,
    cursor: Option<&str>,
    limit: i64,
) -> ApiResult<(Vec<Value>, Option<String>)> {
    let rows = if let Some(cursor) = cursor {
        let (created_at, id) = parse_cursor(cursor)?;
        sqlx::query(event_delta_sql(true))
            .bind(campaign_id)
            .bind(created_at)
            .bind(id)
            .bind(limit)
            .fetch_all(pool)
            .await?
    } else {
        let mut rows = sqlx::query(event_delta_sql(false))
            .bind(campaign_id)
            .bind(limit)
            .fetch_all(pool)
            .await?;
        rows.reverse();
        rows
    };
    let next_cursor = rows
        .last()
        .and_then(|row| {
            cursor_from_parts(
                row.try_get("created_at").ok(),
                row.get::<String, _>("event_id"),
            )
        })
        .or_else(|| cursor.map(str::to_string));
    Ok((rows.into_iter().map(event_json).collect(), next_cursor))
}

fn event_delta_sql(with_cursor: bool) -> &'static str {
    if with_cursor {
        r#"
        SELECT event_id, campaign_id, scene_id, turn_id, actor, event_type,
               visibility, summary, payload, created_at, claimed_at
        FROM events
        WHERE campaign_id = $1 AND (created_at, event_id) > ($2, $3)
        ORDER BY created_at ASC, event_id ASC
        LIMIT $4
        "#
    } else {
        r#"
        SELECT event_id, campaign_id, scene_id, turn_id, actor, event_type,
               visibility, summary, payload, created_at, claimed_at
        FROM events
        WHERE campaign_id = $1
        ORDER BY created_at DESC, event_id DESC
        LIMIT $2
        "#
    }
}

fn event_json(row: sqlx::postgres::PgRow) -> Value {
    json!({
        "event_id": row.get::<String, _>("event_id"),
        "campaign_id": row.get::<String, _>("campaign_id"),
        "scene_id": row.get::<Option<String>, _>("scene_id"),
        "turn_id": row.get::<Option<i32>, _>("turn_id"),
        "actor": row.get::<String, _>("actor"),
        "event_type": row.get::<String, _>("event_type"),
        "visibility": row.get::<String, _>("visibility"),
        "summary": row.get::<String, _>("summary"),
        "payload": object_or_empty(row.try_get("payload").ok()),
        "created_at": iso(row.try_get("created_at").ok()),
        "claimed_at": iso(row.try_get("claimed_at").ok()),
    })
}

pub async fn roll_delta(
    pool: &PgPool,
    campaign_id: &str,
    cursor: Option<&str>,
    limit: i64,
) -> ApiResult<(Vec<Value>, Option<String>)> {
    let rows = if let Some(cursor) = cursor {
        let (created_at, id) = parse_cursor(cursor)?;
        sqlx::query(roll_delta_sql(true))
            .bind(campaign_id)
            .bind(created_at)
            .bind(
                Uuid::parse_str(&id)
                    .map_err(|_| ApiError::BadRequest("invalid roll cursor".into()))?,
            )
            .bind(limit)
            .fetch_all(pool)
            .await?
    } else {
        let mut rows = sqlx::query(roll_delta_sql(false))
            .bind(campaign_id)
            .bind(limit)
            .fetch_all(pool)
            .await?;
        rows.reverse();
        rows
    };
    let next_cursor = rows
        .last()
        .and_then(|row| {
            cursor_from_parts(
                row.try_get("created_at").ok(),
                row.get::<Uuid, _>("id").to_string(),
            )
        })
        .or_else(|| cursor.map(str::to_string));
    Ok((rows.into_iter().map(roll_json).collect(), next_cursor))
}

fn roll_delta_sql(with_cursor: bool) -> &'static str {
    if with_cursor {
        r#"
        SELECT id, campaign_id, session_id, scene_id, character_id, actor, skill,
               attribute, risk, dice, skill_tier, skill_modifier, attribute_tier,
               attribute_modifier, momentum_in, total, target, margin, outcome,
               momentum_delta, momentum_out, target_id, metadata, created_at
        FROM rolls
        WHERE campaign_id = $1 AND (created_at, id) > ($2, $3)
        ORDER BY created_at ASC, id ASC
        LIMIT $4
        "#
    } else {
        r#"
        SELECT id, campaign_id, session_id, scene_id, character_id, actor, skill,
               attribute, risk, dice, skill_tier, skill_modifier, attribute_tier,
               attribute_modifier, momentum_in, total, target, margin, outcome,
               momentum_delta, momentum_out, target_id, metadata, created_at
        FROM rolls
        WHERE campaign_id = $1
        ORDER BY created_at DESC, id DESC
        LIMIT $2
        "#
    }
}

fn roll_json(row: sqlx::postgres::PgRow) -> Value {
    json!({
        "roll_id": row.get::<Uuid, _>("id").to_string(),
        "campaign_id": row.get::<String, _>("campaign_id"),
        "session_id": row.get::<String, _>("session_id"),
        "scene_id": row.get::<Option<String>, _>("scene_id"),
        "character_id": row.get::<String, _>("character_id"),
        "actor": row.get::<String, _>("actor"),
        "skill": row.get::<String, _>("skill"),
        "attribute": row.get::<String, _>("attribute"),
        "risk": row.get::<String, _>("risk"),
        "dice": row.get::<Vec<i32>, _>("dice"),
        "skill_tier": row.get::<String, _>("skill_tier"),
        "skill_modifier": row.get::<i32, _>("skill_modifier"),
        "attribute_tier": row.get::<String, _>("attribute_tier"),
        "attribute_modifier": row.get::<i32, _>("attribute_modifier"),
        "momentum_in": row.get::<i32, _>("momentum_in"),
        "total": row.get::<i32, _>("total"),
        "target": row.get::<i32, _>("target"),
        "margin": row.get::<i32, _>("margin"),
        "outcome": row.get::<String, _>("outcome"),
        "momentum_delta": row.get::<i32, _>("momentum_delta"),
        "momentum_out": row.get::<i32, _>("momentum_out"),
        "target_id": row.get::<Option<String>, _>("target_id"),
        "metadata": object_or_empty(row.try_get("metadata").ok()),
        "created_at": iso(row.try_get("created_at").ok()),
    })
}

pub async fn scene_rows(pool: &PgPool, campaign_id: &str) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(
        r#"
        WITH ranked AS (
            SELECT turn_id, arc_id, scene_id, scene_type, mode, scene_status,
                   ROW_NUMBER() OVER (
                       PARTITION BY arc_id, scene_id
                       ORDER BY turn_id DESC
                   ) AS rn
            FROM turns
            WHERE campaign_id = $1
        )
        SELECT arc_id, scene_id,
               MIN(scene_type) FILTER (WHERE rn = 1) AS scene_type,
               MIN(mode) FILTER (WHERE rn = 1) AS mode,
               MIN(scene_status) FILTER (WHERE rn = 1) AS scene_status,
               MIN(turn_id) AS first_turn_id,
               MAX(turn_id) AS last_turn_id,
               COUNT(*) AS turn_count
        FROM ranked
        GROUP BY arc_id, scene_id
        ORDER BY MIN(turn_id) ASC
        "#,
    )
    .bind(campaign_id)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|row| {
            json!({
                "arc_id": row.get::<Option<String>, _>("arc_id"),
                "scene_id": row.get::<Option<String>, _>("scene_id"),
                "scene_type": row.get::<Option<String>, _>("scene_type"),
                "mode": row.get::<Option<String>, _>("mode"),
                "scene_status": row.get::<Option<String>, _>("scene_status"),
                "first_turn_id": row.get::<i32, _>("first_turn_id"),
                "last_turn_id": row.get::<i32, _>("last_turn_id"),
                "turn_count": row.get::<i64, _>("turn_count"),
            })
        })
        .collect())
}

pub async fn latest_scene(pool: &PgPool, campaign_id: &str) -> ApiResult<Option<Value>> {
    let row = sqlx::query(
        r#"
        SELECT arc_id, scene_id, scene_type
        FROM turns
        WHERE campaign_id = $1
        ORDER BY turn_id DESC
        LIMIT 1
        "#,
    )
    .bind(campaign_id)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|row| {
        json!({
            "arc_id": row.get::<Option<String>, _>("arc_id"),
            "scene_id": row.get::<Option<String>, _>("scene_id"),
            "scene_type": row.get::<Option<String>, _>("scene_type"),
        })
    }))
}
