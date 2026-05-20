use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableFile {
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub section: Option<String>,
    pub title: String,
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size: Option<i64>,
    pub updated_at: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct TablePayload {
    #[serde(default)]
    pub index: Option<TableFile>,
    #[serde(default)]
    pub scene: Option<TableFile>,
    #[serde(default)]
    pub files: Vec<TableFile>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DmSurfacePayload {
    #[serde(default)]
    pub current_scene: Option<Value>,
    #[serde(default)]
    pub beats: Vec<Value>,
    #[serde(default)]
    pub files: Vec<TableFile>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEntry {
    pub path: String,
    pub name: String,
    pub section: String,
    pub title: String,
    pub size: i64,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileIndex {
    #[serde(default)]
    pub files: Vec<FileEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileContent {
    pub campaign_id: String,
    pub path: String,
    pub name: String,
    pub section: String,
    pub title: String,
    pub size: i64,
    pub updated_at: String,
    pub content: String,
}
