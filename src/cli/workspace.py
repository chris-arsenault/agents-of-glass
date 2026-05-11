"""Helpers for arc / scene / lore management within a campaign workspace.

Scaffolds the `campaigns/<id>/arcs/<arc>/...` directory tree, manages the
campaign runtime state (active arc / active scene / arc list), and copies
world-bible entries into the campaign's curated lore.

These helpers are called by the `glass arc`, `glass scene`, and `glass lore`
command groups in main.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import os
import re
import shutil

from .config import get_paths
from .state import load_state, save_state


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unnamed"


@dataclass(frozen=True)
class CampaignWorkspace:
    campaign_id: str
    root: Path

    @property
    def arcs_dir(self) -> Path:
        return self.root / "arcs"

    @property
    def lore_dir(self) -> Path:
        return self.root / "shared" / "lore"

    def arc_dir(self, arc_id: str) -> Path:
        return self.arcs_dir / arc_id

    def scene_dir(self, arc_id: str, scene_id: str) -> Path:
        return self.arc_dir(arc_id) / "scenes" / scene_id

    @property
    def table_dir(self) -> Path:
        return self.root / "table"


def resolve_active_campaign(
    campaigns_dir: Path,
    *,
    explicit_id: str | None = None,
    env_id: str | None = None,
) -> CampaignWorkspace:
    """Find the active campaign workspace.

    Resolution order:
      1. `explicit_id` (e.g. `--campaign foo`)
      2. `env_id` (e.g. `GLASS_CAMPAIGN_ID` env var, set by the orchestrator)
      3. The most-recently-modified campaign directory.
    """
    candidate_id = explicit_id or env_id
    if candidate_id:
        candidate = campaigns_dir / candidate_id
        if not candidate.is_dir():
            raise FileNotFoundError(
                f"Campaign {candidate_id!r} does not exist at {candidate}"
            )
        return CampaignWorkspace(candidate_id, candidate)

    if not campaigns_dir.exists():
        raise FileNotFoundError(
            f"No campaigns directory at {campaigns_dir}; "
            "create one with `aog campaign run <id>`"
        )

    latest: Path | None = None
    for p in campaigns_dir.iterdir():
        if p.is_dir() and not p.name.startswith("."):
            if latest is None or p.stat().st_mtime > latest.stat().st_mtime:
                latest = p
    if latest is None:
        raise FileNotFoundError(
            f"No campaigns found under {campaigns_dir}; "
            "create one with `aog campaign run <id>`"
        )
    return CampaignWorkspace(latest.name, latest)


def load_campaign_state(workspace: CampaignWorkspace) -> dict[str, Any]:
    return load_state(get_paths(), workspace.campaign_id)


def save_campaign_state(workspace: CampaignWorkspace, state: dict[str, Any]) -> None:
    save_state(get_paths(), state)


# --- arcs ---


def create_arc(workspace: CampaignWorkspace, arc_id: str) -> Path:
    arc_id = slugify(arc_id)
    arc_dir = workspace.arc_dir(arc_id)
    if arc_dir.exists():
        raise FileExistsError(f"arc {arc_id!r} already exists at {arc_dir}")

    arc_dir.mkdir(parents=True)
    (arc_dir / "scenes").mkdir()
    (arc_dir / "plan.md").write_text(_arc_plan_stub(arc_id), encoding="utf-8")
    (arc_dir / "context.md").write_text(_arc_context_stub(arc_id), encoding="utf-8")
    (arc_dir / "summary.md").write_text(_arc_summary_stub(arc_id), encoding="utf-8")
    (arc_dir / "clocks.md").write_text(_arc_clocks_stub(arc_id), encoding="utf-8")

    state = load_campaign_state(workspace)
    arcs = state.setdefault("arcs", [])
    if arc_id not in arcs:
        arcs.append(arc_id)
    state["active_arc"] = arc_id
    save_campaign_state(workspace, state)
    return arc_dir


def list_arcs(workspace: CampaignWorkspace) -> list[dict[str, Any]]:
    state = load_campaign_state(workspace)
    out: list[dict[str, Any]] = []
    for arc_id in state.get("arcs", []):
        arc_dir = workspace.arc_dir(arc_id)
        out.append(
            {
                "arc_id": arc_id,
                "active": arc_id == state.get("active_arc"),
                "exists": arc_dir.exists(),
                "path": str(arc_dir),
            }
        )
    return out


def current_arc(workspace: CampaignWorkspace) -> dict[str, Any] | None:
    state = load_campaign_state(workspace)
    arc_id = state.get("active_arc")
    if not arc_id:
        return None
    return {
        "arc_id": arc_id,
        "path": str(workspace.arc_dir(arc_id)),
        "exists": workspace.arc_dir(arc_id).exists(),
    }


def activate_arc(workspace: CampaignWorkspace, arc_id: str) -> Path:
    arc_id = slugify(arc_id)
    arc_dir = workspace.arc_dir(arc_id)
    if not arc_dir.exists():
        raise FileNotFoundError(
            f"arc {arc_id!r} does not exist; run `glass arc create {arc_id}` first"
        )
    state = load_campaign_state(workspace)
    arcs = state.setdefault("arcs", [])
    if arc_id not in arcs:
        arcs.append(arc_id)
    state["active_arc"] = arc_id
    save_campaign_state(workspace, state)
    return arc_dir


# --- scenes ---


def create_scene(
    workspace: CampaignWorkspace,
    scene_id: str,
    scene_type: str,
    arc_id: str | None = None,
) -> Path:
    scene_id = slugify(scene_id)
    if not scene_type.strip():
        raise ValueError("scene type cannot be empty")
    scene_type = slugify(scene_type)

    state = load_campaign_state(workspace)
    previous_scene = state.get("active_scene")
    previous_arc = state.get("active_scene_arc") or state.get("active_arc")
    arc = arc_id or state.get("active_arc")
    if not arc:
        raise ValueError(
            "no active arc and no --arc specified; "
            "run `glass arc create <slug>` first or pass --arc"
        )

    arc_dir = workspace.arc_dir(arc)
    if not arc_dir.exists():
        raise FileNotFoundError(
            f"arc {arc!r} does not exist; run `glass arc create {arc}` first"
        )

    scene_dir = workspace.scene_dir(arc, scene_id)
    if scene_dir.exists():
        raise FileExistsError(f"scene {scene_id!r} already exists at {scene_dir}")

    table_snapshot_path: Path | None = None
    if previous_scene and previous_arc and workspace.table_dir.exists():
        table_snapshot_path = snapshot_table(
            workspace,
            arc_id=str(previous_arc),
            scene_id=str(previous_scene),
            label=f"before-{scene_id}",
        )

    scene_dir.mkdir(parents=True)
    (scene_dir / "prep.md").write_text(
        _scene_prep_stub(scene_id, scene_type), encoding="utf-8"
    )
    (scene_dir / "context.md").write_text(
        _scene_context_stub(scene_id, scene_type), encoding="utf-8"
    )
    (scene_dir / "summary.md").write_text(
        _scene_summary_stub(scene_id, scene_type), encoding="utf-8"
    )
    (scene_dir / "transcript.md").write_text(
        f"# Scene: {scene_id}\n\nType: {scene_type}\n\n", encoding="utf-8"
    )
    (scene_dir / "audit.jsonl").write_text("", encoding="utf-8")
    initialize_table(workspace, scene_id=scene_id, scene_type=scene_type, arc_id=arc)

    state["active_scene"] = scene_id
    state["active_scene_arc"] = arc
    state["active_scene_type"] = scene_type
    if table_snapshot_path:
        state["previous_table_snapshot"] = str(table_snapshot_path)
    save_campaign_state(workspace, state)
    return scene_dir


def end_scene(workspace: CampaignWorkspace) -> str:
    state = load_campaign_state(workspace)
    ended = state.get("active_scene")
    if not ended:
        raise ValueError("no active scene to end")
    state["active_scene"] = None
    state["active_scene_arc"] = None
    state["active_scene_type"] = None
    save_campaign_state(workspace, state)
    return ended


def current_scene(workspace: CampaignWorkspace) -> dict[str, Any] | None:
    state = load_campaign_state(workspace)
    scene_id = state.get("active_scene")
    if not scene_id:
        return None
    arc = state.get("active_scene_arc") or state.get("active_arc")
    return {
        "scene_id": scene_id,
        "arc_id": arc,
        "scene_type": state.get("active_scene_type"),
        "path": str(workspace.scene_dir(arc, scene_id)) if arc else None,
    }


def list_scenes(
    workspace: CampaignWorkspace, arc_id: str | None = None
) -> list[dict[str, Any]]:
    state = load_campaign_state(workspace)
    arc = arc_id or state.get("active_arc")
    if not arc:
        return []
    scenes_root = workspace.arc_dir(arc) / "scenes"
    if not scenes_root.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(scenes_root.iterdir()):
        if not p.is_dir():
            continue
        out.append(
            {
                "scene_id": p.name,
                "arc_id": arc,
                "active": p.name == state.get("active_scene"),
                "path": str(p),
            }
        )
    return out


# --- table ---


def table_dir(workspace: CampaignWorkspace) -> Path:
    return workspace.table_dir


def initialize_table(
    workspace: CampaignWorkspace,
    *,
    scene_id: str,
    scene_type: str,
    arc_id: str,
) -> Path:
    """Create a fresh live table for a top-level scene."""
    root = workspace.table_dir
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / "handouts").mkdir()
    (root / "index.md").write_text(
        _table_index_stub(scene_id=scene_id, scene_type=scene_type, arc_id=arc_id),
        encoding="utf-8",
    )
    (root / "scene.md").write_text(
        _table_scene_stub(scene_id=scene_id, scene_type=scene_type, arc_id=arc_id),
        encoding="utf-8",
    )
    return root


def snapshot_table(
    workspace: CampaignWorkspace,
    *,
    arc_id: str,
    scene_id: str,
    label: str = "snapshot",
) -> Path:
    source = workspace.table_dir
    if not source.exists():
        raise FileNotFoundError(f"no live table at {source}")
    snapshot_root = workspace.scene_dir(arc_id, scene_id) / "table" / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    destination = snapshot_root / f"{_timestamp_slug()}-{slugify(label)}"
    _copy_table(source, destination)
    return destination


def archive_table(
    workspace: CampaignWorkspace,
    *,
    arc_id: str,
    scene_id: str,
    clear_live: bool = True,
) -> Path:
    source = workspace.table_dir
    if not source.exists():
        raise FileNotFoundError(f"no live table at {source}")
    destination = workspace.scene_dir(arc_id, scene_id) / "table" / "final"
    _copy_table(source, destination)
    if clear_live:
        _write_inactive_table(workspace, scene_id=scene_id, archive_path=destination)
    return destination


def _copy_table(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _write_inactive_table(
    workspace: CampaignWorkspace, *, scene_id: str, archive_path: Path
) -> None:
    root = workspace.table_dir
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / "handouts").mkdir()
    rel_archive = archive_path.relative_to(workspace.root)
    (root / "index.md").write_text(
        (
            "---\n"
            "status: inactive\n"
            f"previous_scene: {scene_id}\n"
            f"archive: {rel_archive}\n"
            "---\n\n"
            "# Table\n\n"
            "No scene is currently active.\n\n"
            f"The final table for `{scene_id}` is archived at "
            f"`{rel_archive}`.\n"
        ),
        encoding="utf-8",
    )
    (root / "scene.md").write_text(
        (
            "---\n"
            "status: inactive\n"
            f"previous_scene: {scene_id}\n"
            "---\n\n"
            "# Scene\n\n"
            "No scene is currently active.\n"
        ),
        encoding="utf-8",
    )


def _timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


# --- lore curation ---


def import_lore(
    workspace: CampaignWorkspace,
    lore_path: Path,
    source_root: Path,
    alias: str | None = None,
) -> Path:
    """Copy a world-bible entry into campaigns/<id>/shared/lore/.

    Preserves the entry's path relative to `source_root` (stripping the
    top-level `player/` or `dm/` segment). If `alias` is given, that's used
    as the destination filename instead.
    """
    if not lore_path.is_file():
        raise FileNotFoundError(f"world-bible entry not found: {lore_path}")

    try:
        relative = lore_path.relative_to(source_root)
    except ValueError:
        relative = Path(lore_path.name)

    if alias:
        dest = workspace.lore_dir / Path(alias)
        if not dest.suffix:
            dest = dest.with_suffix(".md")
    else:
        parts = relative.parts
        if parts and parts[0] in ("player", "dm"):
            parts = parts[1:]
        dest = workspace.lore_dir / Path(*parts) if parts else (
            workspace.lore_dir / lore_path.name
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(f"lore entry already exists at destination: {dest}")

    text = lore_path.read_text(encoding="utf-8")
    tagged = _tag_with_source(text, str(relative))
    dest.write_text(tagged, encoding="utf-8")
    return dest


def list_lore(workspace: CampaignWorkspace) -> list[dict[str, Any]]:
    if not workspace.lore_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(workspace.lore_dir.rglob("*.md")):
        rel = p.relative_to(workspace.lore_dir)
        out.append({"path": str(rel), "absolute": str(p)})
    return out


def search_lore(
    source_root: Path, query: str, *, limit: int = 20
) -> list[dict[str, Any]]:
    """Substring search across the world bible (filename + body).

    Intended for the DM to find a candidate entry to `glass lore import`.
    """
    if not source_root.exists():
        return []
    query_lower = query.lower()
    matches: list[dict[str, Any]] = []
    for p in sorted(source_root.rglob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if query_lower not in p.name.lower() and query_lower not in text.lower():
            continue
        preview = ""
        for line in text.splitlines():
            if query_lower in line.lower():
                preview = line.strip()[:160]
                break
        rel = p.relative_to(source_root)
        matches.append({"path": str(rel), "absolute": str(p), "preview": preview})
        if len(matches) >= limit:
            break
    return matches


# --- helpers ---


def _tag_with_source(text: str, source_path: str) -> str:
    """Add `source: world-bible/<path>` to frontmatter (or create it)."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            frontmatter = text[4:end]
            rest = text[end + 5 :]
            if "source:" in frontmatter:
                return text  # already tagged
            new_frontmatter = frontmatter.rstrip() + f"\nsource: world-bible/{source_path}\n"
            return f"---\n{new_frontmatter}---\n{rest}"
    return f"---\nsource: world-bible/{source_path}\n---\n\n{text}"


def _arc_plan_stub(arc_id: str) -> str:
    return (
        f"---\narc_id: {arc_id}\nstatus: stub\n---\n\n"
        f"# Arc Plan: {arc_id}\n\n"
        "DM-only working document. See "
        "[`/templates/methodologies/arc-creation.md`](../../../../templates/methodologies/arc-creation.md) "
        "for the methodology. Fill in each section as you author the arc.\n\n"
        "## 1. Stakes question\n\n_TBD._\n\n"
        "## 2. Threats\n\n_TBD._\n\n"
        "## 3. Clocks\n\n_TBD._\n\n"
        "## 4. Possible end-states\n\n_TBD._\n\n"
        "## 5. Strong start\n\n_TBD._\n\n"
        "## 6. Nodes\n\n_TBD._\n\n"
        "## 7. What from the curated lists is in play\n\n_TBD._\n\n"
        "## 8. Arc-specific secrets\n\n_TBD._\n\n"
        "## 9. Done criteria\n\n_TBD._\n"
    )


def _arc_context_stub(arc_id: str) -> str:
    return (
        f"---\narc_id: {arc_id}\nstatus: stub\n---\n\n"
        f"# Arc: {arc_id}\n\n"
        "_Player-facing summary. Initially terse — DM updates as the arc plays out and players discover more._\n"
    )


def _arc_summary_stub(arc_id: str) -> str:
    return (
        f"---\narc_id: {arc_id}\nstatus: stub\n---\n\n"
        f"# Arc Summary: {arc_id}\n\n"
        "_Running arc summary. Update as scenes resolve and pressures change._\n"
    )


def _arc_clocks_stub(arc_id: str) -> str:
    return (
        "---\n"
        "generated_by: glass clock\n"
        "---\n\n"
        f"# Public Clocks - {arc_id}\n\n"
        "Postgres is canonical. Public arc clocks will be projected here.\n\n"
        "## Active\n\n_None._\n\n"
        "## Resolved\n\n_None._\n"
    )


def _scene_prep_stub(scene_id: str, scene_type: str) -> str:
    return (
        f"---\nscene_id: {scene_id}\nscene_type: {scene_type}\nstatus: stub\n---\n\n"
        f"# Scene Prep: {scene_id}\n\n"
        f"**Scene type:** `{scene_type}`\n\n"
        "DM-only working document. See "
        "[`/templates/methodologies/scene-prep.md`](../../../../../../templates/methodologies/scene-prep.md) "
        "for the methodology.\n\n"
        "## 1. Recap\n\n_TBD._\n\n"
        "## 2. Strong start\n\n_TBD._\n\n"
        "## 3. Possible directions (3-5)\n\n_TBD._\n\n"
        "## 4. NPCs in play\n\n_TBD._\n\n"
        "## 5. Antagonists / creatures / threats\n\n_TBD._\n\n"
        "## 6. Named things in play\n\n_TBD._\n\n"
        "## 7. Secrets that might surface\n\n_TBD._\n\n"
        "## 8. Open questions\n\n_TBD._\n"
    )


def _scene_context_stub(scene_id: str, scene_type: str) -> str:
    return (
        f"---\nscene_id: {scene_id}\nscene_type: {scene_type}\nstatus: stub\n---\n\n"
        f"# Scene: {scene_id}\n\n"
        f"**Type:** `{scene_type}`\n\n"
        "_Player-facing scene framing — locale, who's there, what's happening, what just happened._\n"
    )


def _scene_summary_stub(scene_id: str, scene_type: str) -> str:
    return (
        f"---\nscene_id: {scene_id}\nscene_type: {scene_type}\nstatus: stub\n---\n\n"
        f"# {scene_id} - summary\n\n"
        "_Scene summary is finalized by `glass scene end --summary`._\n"
    )


def _table_index_stub(scene_id: str, scene_type: str, arc_id: str) -> str:
    return (
        "---\n"
        "status: active\n"
        f"arc_id: {arc_id}\n"
        f"scene_id: {scene_id}\n"
        f"scene_type: {scene_type}\n"
        "---\n\n"
        "# Table\n\n"
        f"- **Scene:** `{scene_id}`\n"
        f"- **Type:** `{scene_type}`\n"
        "- **Kickoff:** [`scene.md`](scene.md)\n"
        "- **Handouts:** [`handouts/`](handouts/)\n\n"
        "## At A Glance\n\n"
        "_DM: keep the immediate visible state here. Link any freeform table "
        "root files that players should read before asking for repeated "
        "information._\n\n"
        "## Relevant Table Files\n\n"
        "- [`scene.md`](scene.md)\n\n"
        "## Public Questions\n\n"
        "_Questions the table can answer from visible state, or that the DM "
        "should answer on the next update._\n"
    )


def _table_scene_stub(scene_id: str, scene_type: str, arc_id: str) -> str:
    return (
        "---\n"
        "status: active\n"
        f"arc_id: {arc_id}\n"
        f"scene_id: {scene_id}\n"
        f"scene_type: {scene_type}\n"
        "---\n\n"
        f"# Scene: {scene_id}\n\n"
        "_DM: replace this with the scene kickoff description: where the party "
        "is, what is visible, who or what is present, what is in motion, and "
        "what the players should understand before taking their first turns._\n"
    )
