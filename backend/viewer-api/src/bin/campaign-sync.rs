use std::env;
use std::fs::{self, File, Metadata};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use aws_sdk_s3::Client;
use aws_sdk_s3::primitives::ByteStream;
use base64::Engine;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use chrono::{DateTime, SecondsFormat, Utc};
use serde::Serialize;
use serde_json::{Value, json};
use viewer_api::types::{
    DmSurfacePayload, FileContent, FileEntry, FileIndex, TableFile, TablePayload,
};

const MAX_FILE_BYTES: usize = 512_000;
const READABLE_SUFFIXES: &[&str] = &["jsonl", "md", "txt"];
const EXCLUDED_FILE_NAMES: &[&str] = &[".glass-grants.json"];
const EXCLUDED_PATH_PARTS: &[&str] = &[".git", ".glass-cwd", "__pycache__"];

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse()?;
    let campaign_id = args.campaign_id.clone().unwrap_or_else(|| {
        args.campaign_root
            .file_name()
            .unwrap()
            .to_string_lossy()
            .into()
    });
    validate_campaign_id(&campaign_id)?;

    let files = collect_file_entries(&args.campaign_root)?;
    let table = table_payload(&args.campaign_root, &files)?;
    let dm_surface = dm_surface_payload(&args.campaign_root)?;
    let config = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
    let client = Client::new(&config);

    put_json(
        &client,
        &args,
        &campaign_key(&args.prefix, &campaign_id, "table.json"),
        &table,
    )
    .await?;
    put_json(
        &client,
        &args,
        &campaign_key(&args.prefix, &campaign_id, "dm_surface.json"),
        &dm_surface,
    )
    .await?;
    put_json(
        &client,
        &args,
        &campaign_key(&args.prefix, &campaign_id, "files/index.json"),
        &FileIndex {
            files: files.iter().map(|item| item.entry.clone()).collect(),
        },
    )
    .await?;

    for item in &files {
        let content = FileContent {
            campaign_id: campaign_id.clone(),
            path: item.entry.path.clone(),
            name: item.entry.name.clone(),
            section: item.entry.section.clone(),
            title: item.entry.title.clone(),
            size: item.entry.size,
            updated_at: item.entry.updated_at.clone(),
            content: read_text(&item.local_path)?,
        };
        let encoded = URL_SAFE_NO_PAD.encode(item.entry.path.as_bytes());
        put_json(
            &client,
            &args,
            &campaign_key(
                &args.prefix,
                &campaign_id,
                &format!("files/content/{encoded}.json"),
            ),
            &content,
        )
        .await?;
    }

    println!(
        "published {} campaign files for {} to s3://{}/{}/{}",
        files.len(),
        campaign_id,
        args.bucket,
        args.prefix.trim_matches('/'),
        campaign_id
    );
    Ok(())
}

#[derive(Debug)]
struct Args {
    campaign_root: PathBuf,
    bucket: String,
    prefix: String,
    campaign_id: Option<String>,
    dry_run: bool,
}

impl Args {
    fn parse() -> Result<Self> {
        let mut campaign_root = env::var("CAMPAIGN_ROOT").ok().map(PathBuf::from);
        let mut bucket = env::var("CAMPAIGN_BUCKET").ok();
        let mut prefix = env::var("CAMPAIGN_PREFIX").unwrap_or_else(|_| "campaigns".into());
        let mut campaign_id = env::var("CAMPAIGN_ID").ok();
        let mut dry_run = false;

        let mut args = env::args().skip(1);
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--campaign-root" => campaign_root = Some(next_path(&mut args, "--campaign-root")?),
                "--bucket" => bucket = Some(next_string(&mut args, "--bucket")?),
                "--prefix" => prefix = next_string(&mut args, "--prefix")?,
                "--campaign-id" => campaign_id = Some(next_string(&mut args, "--campaign-id")?),
                "--dry-run" => dry_run = true,
                "-h" | "--help" => {
                    print_usage();
                    std::process::exit(0);
                }
                value => bail!("unknown argument: {value}"),
            }
        }

        let campaign_root = campaign_root.context("missing --campaign-root or CAMPAIGN_ROOT")?;
        let bucket = bucket.context("missing --bucket or CAMPAIGN_BUCKET")?;
        if !campaign_root.is_dir() {
            bail!(
                "campaign root is not a directory: {}",
                campaign_root.display()
            );
        }
        Ok(Self {
            campaign_root,
            bucket,
            prefix,
            campaign_id,
            dry_run,
        })
    }
}

fn next_string(args: &mut impl Iterator<Item = String>, name: &str) -> Result<String> {
    args.next()
        .filter(|value| !value.is_empty())
        .with_context(|| format!("{name} requires a value"))
}

fn next_path(args: &mut impl Iterator<Item = String>, name: &str) -> Result<PathBuf> {
    next_string(args, name).map(PathBuf::from)
}

fn print_usage() {
    let _ = writeln!(
        std::io::stdout(),
        "usage: campaign-sync --campaign-root <path> --bucket <bucket> [--prefix campaigns] [--campaign-id <id>] [--dry-run]"
    );
}

#[derive(Debug, Clone)]
struct PublishedFile {
    local_path: PathBuf,
    entry: FileEntry,
}

fn collect_file_entries(root: &Path) -> Result<Vec<PublishedFile>> {
    let mut files = Vec::new();
    visit_campaign_dir(root, root, &mut files)?;
    files.sort_by(|left, right| left.entry.path.cmp(&right.entry.path));
    Ok(files)
}

fn visit_campaign_dir(root: &Path, dir: &Path, files: &mut Vec<PublishedFile>) -> Result<()> {
    for entry in fs::read_dir(dir).with_context(|| format!("read {}", dir.display()))? {
        let entry = entry?;
        let path = entry.path();
        let metadata = fs::symlink_metadata(&path)?;
        if metadata.file_type().is_symlink() {
            continue;
        }
        if metadata.is_dir() {
            if !path_has_excluded_part(root, &path) {
                visit_campaign_dir(root, &path, files)?;
            }
            continue;
        }
        if is_readable_campaign_file(root, &path, &metadata) {
            files.push(PublishedFile {
                entry: file_entry(root, &path, &metadata)?,
                local_path: path,
            });
        }
    }
    Ok(())
}

fn is_readable_campaign_file(root: &Path, path: &Path, metadata: &Metadata) -> bool {
    if !metadata.is_file() || path_has_excluded_part(root, path) {
        return false;
    }
    if path
        .file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| EXCLUDED_FILE_NAMES.contains(&name))
    {
        return false;
    }
    path.extension()
        .and_then(|value| value.to_str())
        .is_some_and(|suffix| READABLE_SUFFIXES.contains(&suffix.to_ascii_lowercase().as_str()))
}

fn path_has_excluded_part(root: &Path, path: &Path) -> bool {
    path.strip_prefix(root)
        .ok()
        .into_iter()
        .flat_map(|relative| relative.components())
        .filter_map(|part| part.as_os_str().to_str())
        .any(|part| part.starts_with('.') || EXCLUDED_PATH_PARTS.contains(&part))
}

fn file_entry(root: &Path, path: &Path, metadata: &Metadata) -> Result<FileEntry> {
    let relative = path
        .strip_prefix(root)
        .context("file escaped campaign root")?
        .to_string_lossy()
        .replace('\\', "/");
    let name = path
        .file_name()
        .context("file has no name")?
        .to_string_lossy()
        .to_string();
    Ok(FileEntry {
        section: relative.split('/').next().unwrap_or_default().to_string(),
        path: relative,
        name,
        title: file_title(path)?,
        size: i64::try_from(metadata.len()).unwrap_or(i64::MAX),
        updated_at: system_time_iso(metadata.modified()?),
    })
}

fn table_payload(root: &Path, files: &[PublishedFile]) -> Result<TablePayload> {
    Ok(TablePayload {
        index: optional_table_file(root, &root.join("table/index.md"), Some("index.md"))?,
        scene: optional_table_file(root, &root.join("table/scene.md"), Some("scene.md"))?,
        files: files
            .iter()
            .filter(|file| file.entry.path.starts_with("table/"))
            .filter(|file| {
                file.entry.path != "table/index.md" && file.entry.path != "table/scene.md"
            })
            .map(|file| table_file(root, &file.local_path, None))
            .collect::<Result<Vec<_>>>()?,
    })
}

fn optional_table_file(
    root: &Path,
    path: &Path,
    path_override: Option<&str>,
) -> Result<Option<TableFile>> {
    let metadata = match fs::symlink_metadata(path) {
        Ok(metadata) if is_readable_campaign_file(root, path, &metadata) => metadata,
        _ => return Ok(None),
    };
    table_file_with_metadata(root, path, &metadata, path_override).map(Some)
}

fn table_file(root: &Path, path: &Path, path_override: Option<&str>) -> Result<TableFile> {
    let metadata = fs::symlink_metadata(path)?;
    table_file_with_metadata(root, path, &metadata, path_override)
}

fn table_file_with_metadata(
    root: &Path,
    path: &Path,
    metadata: &Metadata,
    path_override: Option<&str>,
) -> Result<TableFile> {
    let entry = file_entry(root, path, metadata)?;
    Ok(TableFile {
        path: path_override.unwrap_or(&entry.path).into(),
        name: Some(entry.name),
        section: Some(entry.section),
        title: entry.title,
        content: read_text(path)?,
        size: Some(entry.size),
        updated_at: entry.updated_at,
    })
}

fn dm_surface_payload(root: &Path) -> Result<DmSurfacePayload> {
    let current_scene = current_scene_from_legacy_state(root)?;
    let files = current_scene
        .as_ref()
        .and_then(|scene| scene.get("path").and_then(Value::as_str))
        .map(|scene_path| root.join(scene_path).join("prep.md"))
        .map(|path| optional_table_file(root, &path, None))
        .transpose()?
        .flatten()
        .into_iter()
        .collect();

    Ok(DmSurfacePayload {
        current_scene,
        beats: quest_beats(&root.join("shared/quest-log.md"), 12)?,
        files,
    })
}

fn current_scene_from_legacy_state(root: &Path) -> Result<Option<Value>> {
    let path = root.join("state.json");
    if !path.is_file() {
        return Ok(None);
    }
    let state: Value = serde_json::from_str(&read_text(&path)?).context("parse state.json")?;
    let Some(scene_id) = state.get("active_scene").and_then(Value::as_str) else {
        return Ok(None);
    };
    let arc_id = state
        .get("active_scene_arc")
        .or_else(|| state.get("active_arc"))
        .and_then(Value::as_str);
    let scene_path = arc_id.map(|arc_id| format!("arcs/{arc_id}/scenes/{scene_id}"));
    Ok(Some(json!({
        "arc_id": arc_id,
        "scene_id": scene_id,
        "scene_type": state.get("active_scene_type").cloned().unwrap_or(Value::Null),
        "path": scene_path,
    })))
}

fn quest_beats(path: &Path, limit: usize) -> Result<Vec<Value>> {
    if !path.is_file() {
        return Ok(Vec::new());
    }
    let mut beats = Vec::new();
    for line in read_text(path)?.lines() {
        let trimmed = line.trim_start();
        if !(trimmed.starts_with("- ") || trimmed.starts_with("* ")) {
            continue;
        }
        let mut rest = trimmed[2..].trim();
        let mut arc_id = None;
        let mut scene_id = None;
        if let Some(tag_end) = rest.strip_prefix('[').and_then(|value| value.find(']')) {
            let tag = &rest[1..=tag_end];
            let mut parts = tag
                .trim_end_matches(']')
                .split(':')
                .filter(|part| !part.is_empty());
            arc_id = parts.next().map(str::to_string);
            scene_id = parts.next().map(str::to_string);
            rest = rest[tag_end + 2..].trim();
        }
        if !rest.is_empty() {
            beats.push(json!({
                "text": rest,
                "arc_id": arc_id,
                "scene_id": scene_id,
                "source_path": "shared/quest-log.md",
            }));
        }
    }
    let keep_from = beats.len().saturating_sub(limit);
    Ok(beats.split_off(keep_from))
}

fn file_title(path: &Path) -> Result<String> {
    for line in read_text(path)?.lines().take(30) {
        let stripped = line.trim();
        if stripped.starts_with('#') {
            let title = stripped.trim_start_matches('#').trim();
            return Ok(non_empty_title(title, path));
        }
        if stripped.to_ascii_lowercase().starts_with("title:") {
            let title = stripped
                .split_once(':')
                .map(|(_, value)| value.trim().trim_matches('"').trim_matches('\''))
                .unwrap_or_default();
            return Ok(non_empty_title(title, path));
        }
    }
    Ok(default_title(path))
}

fn non_empty_title(title: &str, path: &Path) -> String {
    if title.is_empty() {
        default_title(path)
    } else {
        title.to_string()
    }
}

fn default_title(path: &Path) -> String {
    path.file_stem()
        .or_else(|| path.file_name())
        .map(|value| value.to_string_lossy().replace(['-', '_'], " "))
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| "untitled".into())
}

fn read_text(path: &Path) -> Result<String> {
    let mut file = File::open(path).with_context(|| format!("read {}", path.display()))?;
    let mut raw = Vec::with_capacity(MAX_FILE_BYTES + 1);
    std::io::Read::by_ref(&mut file)
        .take((MAX_FILE_BYTES + 1) as u64)
        .read_to_end(&mut raw)?;
    let truncated = raw.len() > MAX_FILE_BYTES;
    if truncated {
        raw.truncate(MAX_FILE_BYTES);
    }
    let mut text = String::from_utf8_lossy(&raw).to_string();
    if truncated {
        text.push_str(&format!("\n\n[truncated at {MAX_FILE_BYTES} bytes]"));
    }
    Ok(text)
}

async fn put_json<T: Serialize>(
    client: &Client,
    args: &Args,
    key: &str,
    payload: &T,
) -> Result<()> {
    let body = serde_json::to_vec(payload)?;
    if args.dry_run {
        println!(
            "dry-run put s3://{}/{} ({} bytes)",
            args.bucket,
            key,
            body.len()
        );
        return Ok(());
    }
    client
        .put_object()
        .bucket(&args.bucket)
        .key(key)
        .content_type("application/json")
        .body(ByteStream::from(body))
        .send()
        .await
        .with_context(|| format!("put s3://{}/{}", args.bucket, key))?;
    Ok(())
}

fn campaign_key(prefix: &str, campaign_id: &str, suffix: &str) -> String {
    format!(
        "{}/{}/{}",
        prefix.trim_matches('/'),
        campaign_id,
        suffix.trim_start_matches('/')
    )
}

fn system_time_iso(time: std::time::SystemTime) -> String {
    DateTime::<Utc>::from(time).to_rfc3339_opts(SecondsFormat::Secs, true)
}

fn validate_campaign_id(campaign_id: &str) -> Result<()> {
    if campaign_id.is_empty()
        || campaign_id == "."
        || campaign_id == ".."
        || campaign_id.starts_with('.')
        || campaign_id.contains('/')
        || campaign_id.contains('\\')
    {
        bail!("invalid campaign id: {campaign_id}");
    }
    Ok(())
}
