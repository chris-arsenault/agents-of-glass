use aws_sdk_s3::Client;
use aws_sdk_s3::error::SdkError;
use aws_sdk_s3::operation::get_object::GetObjectError;
use base64::Engine;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::collections::HashMap;
use std::env;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;

use crate::error::{ApiError, ApiResult};
use crate::types::{DmSurfacePayload, FileContent, FileEntry, FileIndex, TablePayload};

#[derive(Clone)]
pub struct S3Store {
    client: Client,
    bucket: Option<String>,
    prefix: String,
    cache: Arc<RwLock<HashMap<String, CacheEntry>>>,
    cache_ttl: Duration,
    cache_max_entries: usize,
}

#[derive(Clone)]
struct CacheEntry {
    expires_at: Instant,
    body: Option<Vec<u8>>,
}

impl S3Store {
    pub async fn from_env() -> Self {
        let config = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
        Self {
            client: Client::new(&config),
            bucket: env::var("CAMPAIGN_BUCKET")
                .ok()
                .filter(|value| !value.is_empty()),
            prefix: env::var("CAMPAIGN_PREFIX").unwrap_or_else(|_| "campaigns".into()),
            cache: Arc::new(RwLock::new(HashMap::new())),
            cache_ttl: env_duration("S3_CACHE_TTL_SECONDS", 15),
            cache_max_entries: env_usize("S3_CACHE_MAX_ENTRIES", 512),
        }
    }

    pub fn configured(&self) -> bool {
        self.bucket.is_some()
    }

    pub async fn table(&self, campaign_id: &str) -> ApiResult<TablePayload> {
        self.get_json(&self.key(campaign_id, "table.json"))
            .await
            .map(|value| value.unwrap_or_default())
    }

    pub async fn dm_surface(&self, campaign_id: &str) -> ApiResult<DmSurfacePayload> {
        self.get_json(&self.key(campaign_id, "dm_surface.json"))
            .await
            .map(|value| value.unwrap_or_default())
    }

    pub async fn turn_output(&self, campaign_id: &str) -> ApiResult<Option<Value>> {
        self.get_json(&self.key(campaign_id, "turn-output.json"))
            .await
    }

    pub async fn file_index(&self, campaign_id: &str) -> ApiResult<FileIndex> {
        let key = self.key(campaign_id, "files/index.json");
        let value: Option<Value> = self.get_json(&key).await?;
        let Some(value) = value else {
            return Ok(FileIndex { files: Vec::new() });
        };
        if value.is_array() {
            let files = serde_json::from_value(value)
                .map_err(|err| ApiError::Storage(format!("invalid file index: {err}")))?;
            return Ok(FileIndex { files });
        }
        serde_json::from_value(value)
            .map_err(|err| ApiError::Storage(format!("invalid file index: {err}")))
    }

    pub async fn file_content(
        &self,
        campaign_id: &str,
        path: &str,
    ) -> ApiResult<Option<FileContent>> {
        let encoded = URL_SAFE_NO_PAD.encode(path.as_bytes());
        let key = self.key(campaign_id, &format!("files/content/{encoded}.json"));
        self.get_json(&key).await
    }

    pub async fn published_file_paths(&self, campaign_id: &str) -> ApiResult<Vec<String>> {
        Ok(self
            .file_index(campaign_id)
            .await?
            .files
            .into_iter()
            .map(|entry| entry.path)
            .collect())
    }

    async fn get_json<T: DeserializeOwned>(&self, key: &str) -> ApiResult<Option<T>> {
        let Some(bucket) = &self.bucket else {
            return Ok(None);
        };
        if let Some(cached) = self.cached_body(key).await {
            return decode_json(key, cached.as_deref());
        }

        let response = self
            .client
            .get_object()
            .bucket(bucket)
            .key(key)
            .send()
            .await;
        let response = match response {
            Ok(value) => value,
            Err(SdkError::ServiceError(err)) if is_not_found(err.err()) => {
                self.put_cache(key, None).await;
                return Ok(None);
            }
            Err(err) => return Err(ApiError::Storage(format!("S3 get {key} failed: {err}"))),
        };
        let bytes = response
            .body
            .collect()
            .await
            .map_err(|err| ApiError::Storage(format!("S3 read {key} failed: {err}")))?
            .into_bytes();
        self.put_cache(key, Some(bytes.to_vec())).await;
        decode_json(key, Some(bytes.as_ref()))
    }

    fn key(&self, campaign_id: &str, suffix: &str) -> String {
        format!(
            "{}/{}/{}",
            self.prefix.trim_matches('/'),
            campaign_id,
            suffix.trim_start_matches('/')
        )
    }

    async fn cached_body(&self, key: &str) -> Option<Option<Vec<u8>>> {
        if self.cache_ttl.is_zero() {
            return None;
        }
        let entry = self.cache.read().await.get(key).cloned()?;
        if entry.expires_at > Instant::now() {
            return Some(entry.body);
        }
        self.cache.write().await.remove(key);
        None
    }

    async fn put_cache(&self, key: &str, body: Option<Vec<u8>>) {
        if self.cache_ttl.is_zero() || self.cache_max_entries == 0 {
            return;
        }
        let mut cache = self.cache.write().await;
        if cache.len() >= self.cache_max_entries
            && let Some(expired_key) = cache
                .iter()
                .find(|(_, entry)| entry.expires_at <= Instant::now())
                .map(|(key, _)| key.clone())
                .or_else(|| cache.keys().next().cloned())
        {
            cache.remove(&expired_key);
        }
        cache.insert(
            key.to_string(),
            CacheEntry {
                expires_at: Instant::now() + self.cache_ttl,
                body,
            },
        );
    }
}

fn decode_json<T: DeserializeOwned>(key: &str, body: Option<&[u8]>) -> ApiResult<Option<T>> {
    let Some(body) = body else {
        return Ok(None);
    };
    serde_json::from_slice(body)
        .map(Some)
        .map_err(|err| ApiError::Storage(format!("invalid JSON at {key}: {err}")))
}

fn env_duration(name: &str, default_secs: u64) -> Duration {
    env::var(name)
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .map(Duration::from_secs)
        .unwrap_or_else(|| Duration::from_secs(default_secs))
}

fn env_usize(name: &str, default_value: usize) -> usize {
    env::var(name)
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(default_value)
}

pub fn file_sections(files: &[FileEntry]) -> Vec<Value> {
    FILE_SECTIONS
        .iter()
        .map(|(section, terms)| {
            let count = files
                .iter()
                .filter(|entry| file_matches_terms(entry, terms))
                .count();
            serde_json::json!({ "section": section, "count": count })
        })
        .collect()
}

pub fn file_matches_section(entry: &FileEntry, section: &str) -> bool {
    let fallback_terms = [section];
    let terms = FILE_SECTIONS
        .iter()
        .find(|(name, _)| *name == section)
        .map(|(_, terms)| *terms)
        .unwrap_or(&fallback_terms);
    file_matches_terms(entry, terms)
}

fn file_matches_terms(entry: &FileEntry, terms: &[&str]) -> bool {
    let haystack = format!("{} {} {}", entry.path, entry.title, entry.section).to_lowercase();
    terms
        .iter()
        .any(|term| haystack.contains(&term.to_lowercase()))
}

fn is_not_found(err: &GetObjectError) -> bool {
    matches!(err, GetObjectError::NoSuchKey(_))
}

const FILE_SECTIONS: &[(&str, &[&str])] = &[
    ("journal", &["journal", "players/"]),
    ("lore", &["lore", "context", "summary"]),
    ("arcs", &["arc", "previous"]),
    ("scenes", &["scene", "table/scene", "transcript"]),
    ("dm", &["dm/", "scratchpad", "prep"]),
    ("audit", &["audit", ".jsonl"]),
];
