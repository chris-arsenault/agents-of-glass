import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from cli import db as _db
from cli.commands.character import (
    _append_signature_move,
    _inventory_add,
    _normalize_bulk_update_payload,
    _normalize_goals,
    _render_public_character_mirror,
    _signature_move_names,
    _signature_move_slots,
    _validate_starting_skill_budget,
)
from cli.config import Paths
from cli.config import get_paths, load_config
from cli.errors import GlassError
from cli.local_env import load_repo_env
from cli.embeddings import EmbeddingBatch
from cli.main import main
from cli.messages import load_message_types
from cli.state import load_state


def make_env(tmp_path: Path, campaign_id: str = "c1") -> dict[str, str]:
    templates = tmp_path / "templates"
    campaigns = tmp_path / "campaigns"
    templates.mkdir()
    campaign = campaigns / campaign_id
    campaign.mkdir(parents=True)
    config = tmp_path / "agents-of-glass.toml"
    config.write_text(
        f"""
[postgres]
host = "192.168.66.3"
port = 5432
database = "agents_of_glass"
user = "agents_of_glass_app"

[falkordb]
host = "192.168.66.3"
port = 16379
graph = "agents_of_glass"

[paths]
templates = "{templates}"
campaigns = "{campaigns}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    reset_postgres_runtime(config, campaign_id)
    return {"GLASS_CONFIG": str(config), "GLASS_CAMPAIGN_ID": campaign_id}


def reset_postgres_runtime(config: Path, campaign_id: str) -> None:
    load_repo_env()
    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = str(config)
    try:
        toml_data = load_config()
        pg_config = _db.load_pg_config(toml_data)
        with _db.connect(pg_config) as conn:
            _db.migrate(conn)
            _db.delete_campaign_data(conn, campaign_id)
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def runtime_state(env: dict[str, str]) -> dict:
    previous = os.environ.get("GLASS_CONFIG")
    os.environ["GLASS_CONFIG"] = env["GLASS_CONFIG"]
    try:
        return load_state(get_paths(), env["GLASS_CAMPAIGN_ID"])
    finally:
        if previous is None:
            os.environ.pop("GLASS_CONFIG", None)
        else:
            os.environ["GLASS_CONFIG"] = previous


def invoke_ok(runner: CliRunner, args: list[str], env: dict[str, str]):
    result = runner.invoke(main, args, env=env)
    if result.exit_code != 0:
        raise AssertionError(result.output)
    return result


def create_test_character(
    runner: CliRunner,
    env: dict[str, str],
    *,
    player: str = "tev",
    character_id: str = "vel",
    name: str = "Vel Arannis",
) -> None:
    invoke_ok(
        runner,
        [
            "character",
            "new",
            character_id,
            "--player",
            player,
            "--name",
            name,
            "--species",
            "human",
            "--culture",
            "Sithari",
            "--archetype",
            "resonance knight",
            "--org-role",
            "field witness",
            "--bio",
            "Keeps doors open for people who cannot be seen asking.",
            "--goal",
            "Get Mara safe passage.",
            "--goal",
            "Pay down the route debt.",
            "--skill",
            "spar reading=artisan",
            "--skill",
            "line work=apprentice",
            "--skill",
            "dock talk=apprentice",
        ],
        {**env, "GLASS_ROLE": f"player:{player}"},
    )


class GlassCliTests(unittest.TestCase):
    def test_character_goal_validation_requires_two_or_three_goals(self) -> None:
        self.assertEqual(_normalize_goals(("Find Rin.", "Pay the debt.")), [
            "Find Rin.",
            "Pay the debt.",
        ])
        with self.assertRaises(GlassError):
            _normalize_goals(("Only one.",))
        with self.assertRaises(GlassError):
            _normalize_goals(("one", "two", "three", "four"))

    def test_starting_skill_budget_requires_two_apprentice_one_artisan(self) -> None:
        _validate_starting_skill_budget(
            {
                "low-angle document reading": "artisan",
                "dockyard talk": "apprentice",
                "route weather guessing": "apprentice",
            }
        )

        with self.assertRaises(GlassError):
            _validate_starting_skill_budget(
                {
                    "low-angle document reading": "virtuoso",
                    "dockyard talk": "artisan",
                    "route weather guessing": "apprentice",
                }
            )

        with self.assertRaises(GlassError):
            _validate_starting_skill_budget(
                {
                    "low-angle document reading": "artisan",
                    "dockyard talk": "apprentice",
                }
            )

    def test_character_public_mirror_has_consistent_canonical_fields(self) -> None:
        body = _render_public_character_mirror(
            {
                "character_id": "vel",
                "player_id": "tev",
                "name": "Vel Arannis",
                "species": "human",
                "culture": "Sithari",
                "archetype": "route contact",
                "organization_role": "witness handler",
                "pronouns": "",
                "bio": "Keeps doors open for people who cannot be seen asking.",
                "goals": ["Get Mara safe passage.", "Pay down the route debt."],
                "attributes": {"vitality": "standard", "finesse": "advanced"},
                "skills": {"quiet entry": "artisan"},
                "inventory": [
                    {
                        "id": "forged-route-seal",
                        "qty": 1,
                        "effect_tags": ["passes casual inspection"],
                    }
                ],
                "tags": ["human", "sithari"],
                "hp": {"current": 10, "max": 10},
                "momentum": {"current": 0, "floor": -2, "ceiling": 3},
                "xp": 0,
                "level": 1,
            }
        )

        self.assertIn("type: character-display", body)
        self.assertIn("**Species:** human", body)
        self.assertIn("**Culture:** Sithari", body)
        self.assertIn("**Organization role:** witness handler", body)
        self.assertIn("**Pronouns:** unspecified", body)
        self.assertIn("- Get Mara safe passage.", body)
        self.assertIn("forged-route-seal", body)

    def test_signature_move_slots_progress_by_level(self) -> None:
        self.assertEqual(_signature_move_slots(1), 1)
        self.assertEqual(_signature_move_slots(2), 1)
        self.assertEqual(_signature_move_slots(3), 2)
        self.assertEqual(_signature_move_slots(5), 3)
        self.assertEqual(_signature_move_slots(9), 5)
        self.assertEqual(_signature_move_slots(10), 5)

    def test_signature_move_parser_ignores_template_placeholder(self) -> None:
        body = """
# Signature Moves

## Moves

### Move name

- **Look:** Placeholder.

### Crackling Punch

- **Look:** Sparks down the wrist.
""".strip()

        self.assertEqual(_signature_move_names(body), ["Crackling Punch"])

    def test_signature_move_append_replaces_placeholder(self) -> None:
        body = """
# Signature Moves

## Moves

### Move name

- **Look:** Placeholder.
- **Usual use:** Placeholder.
""".strip()

        updated = _append_signature_move(
            body,
            {"name": "Vel Arannis"},
            "Quiet Door",
            "- **Look:** The latch clicks under a breath.\n"
            "- **Usual use:** Entering places where asking would fail.\n"
            "- **Tells/costs:** Leaves wax dust on the thumb.",
        )

        self.assertNotIn("### Move name", updated)
        self.assertIn("### Quiet Door", updated)
        self.assertIn("wax dust", updated)

    def test_character_bulk_update_payload_normalizes_batched_mutations(self) -> None:
        updates = _normalize_bulk_update_payload(
            {
                "mirror": True,
                "characters": [
                    {
                        "character_id": "vel",
                        "set": {"bio": "Keeps doors open."},
                        "inventory_add": [
                            {
                                "id": "route-seal",
                                "qty": 1,
                                "effect_tags": "passes casual review",
                            }
                        ],
                        "signature_moves": [
                            {
                                "name": "Quiet Door",
                                "look": "A hand on the latch.",
                                "use": "Entering quietly.",
                                "tell": "Wax on the thumb.",
                            }
                        ],
                    }
                ],
            },
            mirror_override=None,
        )

        self.assertEqual(len(updates), 1)
        update = updates[0]
        self.assertEqual(update["character_id"], "vel")
        self.assertTrue(update["mirror"])
        self.assertEqual(update["set"], {"bio": "Keeps doors open."})
        self.assertEqual(update["inventory_add"][0]["effect_tags"], ["passes casual review"])
        self.assertEqual(update["signature_moves"][0]["name"], "Quiet Door")
        self.assertIn("A hand on the latch.", update["signature_moves"][0]["body"])

    def test_inventory_add_merges_qty_and_effect_tags(self) -> None:
        inventory = [{"id": "route-seal", "qty": 1, "effect_tags": ["official"]}]

        change = _inventory_add(
            inventory,
            {"id": "route-seal", "qty": 2, "effect_tags": ["official", "forged"]},
        )

        self.assertEqual(change["qty_before"], 1)
        self.assertEqual(change["qty_after"], 3)
        self.assertEqual(inventory[0]["qty"], 3)
        self.assertEqual(inventory[0]["effect_tags"], ["official", "forged"])

    def test_character_bulk_get_all_lists_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            create_test_character(runner, env, player="tev", character_id="vel")
            create_test_character(
                runner,
                env,
                player="sumi",
                character_id="drova",
                name="Drova Korvanis",
            )

            result = invoke_ok(runner, ["character", "bulk-get", "--all"], env)

            self.assertIn("count: 2", result.output)
            self.assertIn("character_id: vel", result.output)
            self.assertIn("character_id: drova", result.output)

    def test_character_mutations_refresh_public_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            create_test_character(runner, env, player="tev", character_id="vel")

            invoke_ok(runner, ["character", "award-xp", "vel", "2"], dm_env)
            mirror_path = (
                tmp_path
                / "campaigns"
                / "c1"
                / "players"
                / "tev"
                / "public"
                / "character.md"
            )
            self.assertIn("**Level:** 1 (2 XP)", mirror_path.read_text(encoding="utf-8"))

            with patch("cli.commands.roll.random.SystemRandom") as system_random:
                system_random.return_value.randint.side_effect = [6, 6]
                invoke_ok(
                    runner,
                    [
                        "roll",
                        "spar reading",
                        "ingenuity",
                        "--risk",
                        "controlled",
                        "--character",
                        "vel",
                    ],
                    {**env, "GLASS_ROLE": "player:tev"},
                )

            mirror = mirror_path.read_text(encoding="utf-8")
            self.assertIn("**Level:** 1 (2 XP)", mirror)
            self.assertIn("**Momentum:** 2 (-2 to 3)", mirror)

    def test_character_mirror_does_not_queue_turn_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            create_test_character(runner, env, player="tev", character_id="vel")
            before_count = len(runtime_state(env)["pending_events"])

            invoke_ok(
                runner,
                ["character", "mirror", "vel"],
                {**env, "GLASS_ROLE": "player:tev"},
            )

            self.assertEqual(len(runtime_state(env)["pending_events"]), before_count)

    def test_message_types_load_from_instruction_headings_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instructions = root / "instructions"
            instructions.mkdir()
            (instructions / "message-bus.md").write_text(
                """
# Message Bus

Recipients are `dm`, `party`, or a player id.

## Types

### `table-talk`

### `banter`

### `plot-hint`
""".strip()
                + "\n",
                encoding="utf-8",
            )

            found = load_message_types(Paths(content=root, campaigns=root / "campaigns"))

            self.assertEqual(found, {"banter", "plot-hint", "table-talk"})

    def test_session_and_mode_use_campaign_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)

            session = invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            self.assertIn("campaign: c1", session.output)

            mode = invoke_ok(
                runner,
                ["mode", "start", "scene-play", "opening"],
                {**env, "GLASS_ROLE": "dm"},
            )
            self.assertIn("current_mode: scene-play", mode.output)

            state = runtime_state(env)
            self.assertEqual(state["mode_stack"][-1]["mode"], "scene-play")

            ended = invoke_ok(runner, ["mode", "end"], {**env, "GLASS_ROLE": "dm"})
            self.assertIn("ended:", ended.output)

    def test_player_note_write_targets_campaign_not_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            result = invoke_ok(
                runner,
                ["note", "write", "journal/field-note.md", "--body", "Observed."],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("players/tev/journal/field-note.md", result.output)
            campaign_note = (
                tmp_path / "campaigns" / "c1" / "players" / "tev"
                / "journal" / "field-note.md"
            )
            template_note = (
                tmp_path / "templates" / "players" / "tev"
                / "journal" / "field-note.md"
            )
            self.assertEqual(campaign_note.read_text(encoding="utf-8"), "Observed.")
            self.assertFalse(template_note.exists())

    def test_player_note_write_cannot_bypass_signature_move_progression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            result = runner.invoke(
                main,
                ["note", "write", "signature-moves.md", "--body", "Too many moves."],
                env={**env, "GLASS_ROLE": "player:tev"},
            )

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("glass character signature-add", result.output)

    def test_turn_append_exports_file_and_structured_feed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            turn_file = tmp_path / "turn.md"
            turn_file.write_text("Mara frames the scene.", encoding="utf-8")

            appended = invoke_ok(
                runner,
                ["turn", "append", str(turn_file), "--speaker", "dm"],
                dm_env,
            )
            self.assertIn("turn_id: 1", appended.output)
            self.assertIn("transcript_export_path:", appended.output)

            found = invoke_ok(runner, ["turns", "find", "--limit", "1"], dm_env)
            self.assertIn("Mara frames the scene.", found.output)
            text_found = invoke_ok(
                runner,
                ["turns", "find", "--text", "frames", "--limit", "1"],
                dm_env,
            )
            self.assertIn("Mara frames the scene.", text_found.output)

            feed = invoke_ok(runner, ["turns", "feed", "--after-turn", "0"], dm_env)
            self.assertIn("event_type: turn.committed", feed.output)
            self.assertIn('prose: "Mara frames the scene."', feed.output)

            transcript = (tmp_path / "campaigns" / "c1" / "transcript.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Turn 1 - dm (dm) - scene-play, opening", transcript)
            self.assertIn("Mara frames the scene.", transcript)

    def test_sync_apply_commits_projected_paths_and_directories(self) -> None:
        fake_embedding = EmbeddingBatch(
            vectors=[[1.0] + [0.0] * 767],
            model="test-embedding",
            provider="test",
            dimensions=768,
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["arc", "create", "opening"], dm_env)
            with runner.isolated_filesystem(temp_dir=tmp_path):
                (Path("dm") / "workspace").mkdir(parents=True)
                (Path("dm") / "workspace" / "sync-note.md").write_text(
                    "DM note from projected workspace.\n",
                    encoding="utf-8",
                )
                (Path("table")).mkdir()
                (Path("table") / "index.md").write_text(
                    "Visible table update.\n",
                    encoding="utf-8",
                )
                (Path("arcs") / "opening").mkdir(parents=True)
                (Path("arcs") / "opening" / "plan.md").write_text(
                    "Projected arc plan.\n",
                    encoding="utf-8",
                )
                Path("summary.md").write_text(
                    "Campaign summary update.\n",
                    encoding="utf-8",
                )
                with patch("cli.embeddings.embed_text", return_value=fake_embedding):
                    result = invoke_ok(
                        runner,
                        [
                            "sync",
                            "apply",
                            "dm/workspace/sync-note.md",
                            "table",
                            "arcs/opening",
                            "summary.md",
                        ],
                        dm_env,
                    )

            self.assertIn("count: 4", result.output)
            root = tmp_path / "campaigns" / "c1"
            self.assertEqual(
                (root / "dm" / "workspace" / "sync-note.md").read_text(encoding="utf-8"),
                "DM note from projected workspace.\n",
            )
            self.assertEqual(
                (root / "table" / "index.md").read_text(encoding="utf-8"),
                "Visible table update.\n",
            )
            self.assertEqual(
                (root / "arcs" / "opening" / "plan.md").read_text(encoding="utf-8"),
                "Projected arc plan.\n",
            )
            self.assertEqual(
                (root / "summary.md").read_text(encoding="utf-8"),
                "Campaign summary update.\n",
            )
            indexed = invoke_ok(
                runner,
                ["search", "text", "Visible table update", "--type", "markdown"],
                dm_env,
            )
            self.assertIn("table/index.md", indexed.output)

    def test_table_write_refreshes_projected_manifest_path(self) -> None:
        fake_embedding = EmbeddingBatch(
            vectors=[[1.0] + [0.0] * 767],
            model="test-embedding",
            provider="test",
            dimensions=768,
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            with runner.isolated_filesystem(temp_dir=tmp_path):
                Path(".glass-projection-manifest.json").write_text(
                    json.dumps({"files": {"table/index.md": "old-hash"}}),
                    encoding="utf-8",
                )
                Path("table").mkdir()
                (Path("table") / "index.md").write_text(
                    "stale projected edit\n",
                    encoding="utf-8",
                )
                with patch("cli.embeddings.embed_text", return_value=fake_embedding):
                    invoke_ok(
                        runner,
                        [
                            "table",
                            "write",
                            "table/index.md",
                            "--body",
                            "canonical table\n",
                        ],
                        dm_env,
                    )

                self.assertEqual(
                    (Path("table") / "index.md").read_text(encoding="utf-8"),
                    "canonical table\n",
                )
                manifest = json.loads(
                    Path(".glass-projection-manifest.json").read_text(encoding="utf-8")
                )
                self.assertNotEqual(manifest["files"]["table/index.md"], "old-hash")

    def test_semantic_search_ranks_by_embeddings(self) -> None:
        def fake_embed_text(text: str, *, kind: str, config=None) -> EmbeddingBatch:
            lowered = text.lower()
            vector = [0.0] * 768
            vector[0 if "castle" in lowered else 1] = 1.0
            return EmbeddingBatch(
                vectors=[vector],
                model="test-embedding",
                provider="test",
                dimensions=768,
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            castle_turn = tmp_path / "castle.md"
            castle_turn.write_text("The castle gate opens for the party.", encoding="utf-8")
            river_turn = tmp_path / "river.md"
            river_turn.write_text("The river barge slips into fog.", encoding="utf-8")

            with patch("cli.embeddings.embed_text", side_effect=fake_embed_text):
                invoke_ok(
                    runner,
                    ["turn", "append", str(castle_turn), "--speaker", "dm"],
                    dm_env,
                )
                invoke_ok(
                    runner,
                    ["turn", "append", str(river_turn), "--speaker", "dm"],
                    dm_env,
                )
                result = invoke_ok(
                    runner,
                    ["search", "semantic", "castle access", "--type", "turn", "--limit", "2"],
                    dm_env,
                )

            self.assertIn("mode: semantic", result.output)
            self.assertIn("model: test-embedding", result.output)
            self.assertLess(
                result.output.find("castle gate"),
                result.output.find("river barge"),
            )

    def test_turn_initiative_persists_action_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "action", "ambush"], dm_env)

            result = invoke_ok(
                runner,
                ["turn", "initiative", "--participants", "tev,dm,kit"],
                dm_env,
            )

            self.assertIn("action_order:", result.output)
            state = runtime_state(env)
            action_order = state["action_order"]
            self.assertEqual(action_order["mode"], "action")
            self.assertEqual(action_order["scene_id"], "ambush")
            self.assertEqual(action_order["round"], 1)
            self.assertEqual(action_order["cursor"], 0)
            self.assertEqual(set(action_order["order"]), {"tev", "dm", "kit"})
            self.assertEqual(len(action_order["rolls"]), 3)

    def test_arc_activate_switches_current_arc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            invoke_ok(runner, ["arc", "create", "main-opening"], dm_env)
            invoke_ok(runner, ["arc", "create", "prelude"], dm_env)
            current = invoke_ok(runner, ["arc", "current"], dm_env)
            self.assertIn("prelude", current.output)

            activated = invoke_ok(runner, ["arc", "activate", "main-opening"], dm_env)

            self.assertIn("main-opening", activated.output)
            state = runtime_state(env)
            self.assertEqual(state["active_arc"], "main-opening")

    def test_scene_create_accepts_custom_type_and_trackers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["arc", "create", "first-arc"], dm_env)

            scene = invoke_ok(
                runner,
                ["scene", "create", "duke-gate", "--type", "courtroom-standoff"],
                dm_env,
            )
            self.assertIn("scene_type: courtroom-standoff", scene.output)
            root = tmp_path / "campaigns" / "c1"
            table_root = root / "table"
            self.assertTrue((table_root / "index.md").exists())
            self.assertTrue((table_root / "scene.md").exists())
            self.assertTrue((table_root / "handouts").is_dir())
            self.assertIn("table_path:", scene.output)

            invoke_ok(
                runner,
                [
                    "table",
                    "write",
                    "npc-korth.md",
                    "--body",
                    "Korth is visibly rattled.",
                ],
                dm_env,
            )
            table_read = invoke_ok(
                runner,
                ["table", "show", "npc-korth.md"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("Korth is visibly rattled.", table_read.output)
            denied = runner.invoke(
                main,
                ["table", "write", "player-note.md", "--body", "not allowed"],
                env={**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertNotEqual(denied.exit_code, 0)
            self.assertIn("DM-only", denied.output)

            invoke_ok(runner, ["mode", "start", "action", "duke-gate"], dm_env)
            turn_file = tmp_path / "scene-turn.md"
            turn_file.write_text("Mara points to the castle gate.", encoding="utf-8")
            invoke_ok(
                runner,
                ["turn", "append", str(turn_file), "--speaker", "dm"],
                dm_env,
            )
            scene_transcript = (
                root / "arcs" / "first-arc" / "scenes" / "duke-gate" / "transcript.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Mara points to the castle gate.", scene_transcript)

            tracker = invoke_ok(
                runner,
                [
                    "scene",
                    "tracker",
                    "set",
                    "duke-permission",
                    "--label",
                    "Duke lets the party into the castle",
                    "--max",
                    "4",
                    "--resistance",
                    "2",
                    "--impact-resistance",
                    "1",
                ],
                dm_env,
            )
            self.assertIn("Duke lets the party into the castle", tracker.output)
            ticked = invoke_ok(
                runner,
                ["scene", "tracker", "tick", "duke-permission", "2"],
                dm_env,
            )
            self.assertIn("after: 2", ticked.output)

            state = runtime_state(env)
            self.assertEqual(state["active_scene_type"], "courtroom-standoff")
            self.assertEqual(state["scene_trackers"]["duke-permission"]["value"], 2)
            self.assertEqual(state["scene_trackers"]["duke-permission"]["resistance"], 2)
            self.assertEqual(
                state["scene_trackers"]["duke-permission"]["impact_resistance"],
                1,
            )

            snapshot = invoke_ok(
                runner,
                ["table", "snapshot", "--label", "after-korth"],
                dm_env,
            )
            self.assertIn("after-korth", snapshot.output)

    def test_players_can_append_only_to_active_scene_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["arc", "create", "first-arc"], dm_env)
            invoke_ok(runner, ["scene", "create", "opening", "--type", "social"], dm_env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)

            appended = invoke_ok(
                runner,
                [
                    "summary",
                    "append",
                    "scene",
                    "--body",
                    "- Turn 2: Tev asks Inka what the packet means.",
                ],
                player_env,
            )
            self.assertIn("level: scene", appended.output)
            summary = (
                tmp_path / "campaigns" / "c1" / "arcs" / "first-arc"
                / "scenes" / "opening" / "summary.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Tev asks Inka", summary)

            denied_write = runner.invoke(
                main,
                ["summary", "write", "scene", "--body", "replace"],
                env=player_env,
            )
            self.assertNotEqual(denied_write.exit_code, 0)
            self.assertIn("players may only append", denied_write.output)

            denied_campaign = runner.invoke(
                main,
                ["summary", "append", "campaign", "--body", "not allowed"],
                env=player_env,
            )
            self.assertNotEqual(denied_campaign.exit_code, 0)
            self.assertIn("players may only append", denied_campaign.output)

            denied_long = runner.invoke(
                main,
                ["summary", "append", "scene", "--body", "x" * 1501],
                env=player_env,
            )
            self.assertNotEqual(denied_long.exit_code, 0)
            self.assertIn("scene summary append is too long", denied_long.output)

    def test_arc_scene_quest_and_scene_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            arc = invoke_ok(runner, ["arc", "create", "first-arc"], dm_env)
            self.assertIn("arc_id: first-arc", arc.output)

            scene = invoke_ok(
                runner,
                ["scene", "create", "opening", "--type", "social"],
                dm_env,
            )
            self.assertIn("scene_id: opening", scene.output)
            invoke_ok(
                runner,
                [
                    "table",
                    "append",
                    "index.md",
                    "--body",
                    "\n- The warrant clock is visible on the table.\n",
                ],
                dm_env,
            )

            beat = invoke_ok(
                runner,
                ["quest", "beat", "The warrant clock starts."],
                dm_env,
            )
            self.assertIn("The warrant clock starts.", beat.output)

            ended = invoke_ok(
                runner,
                [
                    "scene",
                    "end",
                    "--summary",
                    "The scene closes.",
                    "--outcome",
                    "The warrant is now the party's chosen burden.",
                    "--beats",
                    "The party commits to the warrant.",
                ],
                dm_env,
            )
            self.assertIn("ended_scene: opening", ended.output)
            self.assertIn("The warrant is now the party's chosen burden.", ended.output)

            root = tmp_path / "campaigns" / "c1"
            quest_log = (root / "shared" / "quest-log.md").read_text(encoding="utf-8")
            self.assertIn("The warrant clock starts.", quest_log)
            self.assertIn("The party commits to the warrant.", quest_log)
            summary = (
                root / "arcs" / "first-arc" / "scenes" / "opening" / "summary.md"
            ).read_text(encoding="utf-8")
            self.assertIn("The scene closes.", summary)
            self.assertIn("## Outcomes", summary)
            self.assertIn("The warrant is now the party's chosen burden.", summary)
            shown_summary = invoke_ok(
                runner,
                ["summary", "show", "scene", "opening", "--arc", "first-arc"],
                dm_env,
            )
            self.assertIn("The scene closes.", shown_summary.output)
            invoke_ok(
                runner,
                ["summary", "write", "campaign", "--body", "The campaign has begun."],
                dm_env,
            )
            campaign_summary = invoke_ok(
                runner,
                ["summary", "show", "campaign"],
                {**env, "GLASS_ROLE": "player:tev"},
            )
            self.assertIn("The campaign has begun.", campaign_summary.output)
            archived_table = root / "arcs" / "first-arc" / "scenes" / "opening" / "table" / "final"
            self.assertTrue((archived_table / "index.md").exists())
            self.assertIn(
                "The warrant clock is visible",
                (archived_table / "index.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "No scene is currently active",
                (root / "table" / "index.md").read_text(encoding="utf-8"),
            )

            closed = invoke_ok(
                runner,
                [
                    "arc",
                    "close",
                    "first-arc",
                    "--summary",
                    "The opening act closes around the warrant.",
                    "--outcome",
                    "The warrant enters party history as a public commitment.",
                    "--outcome",
                    "The Council has a reason to answer them.",
                ],
                dm_env,
            )
            self.assertIn("closed_arc: first-arc", closed.output)
            arc_summary = (
                root / "arcs" / "first-arc" / "summary.md"
            ).read_text(encoding="utf-8")
            self.assertIn("The opening act closes around the warrant.", arc_summary)
            self.assertIn("## Outcomes", arc_summary)
            self.assertIn(
                "The warrant enters party history as a public commitment.",
                arc_summary,
            )


if __name__ == "__main__":
    unittest.main()
