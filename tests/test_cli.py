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
    _normalize_life_prompt_answers,
    _render_public_character_mirror,
    _require_pull_utilization_note,
    _signature_move_names,
    _signature_move_slots,
    _validate_starting_skill_budget,
)
from cli.config import Paths
from cli.config import get_paths, load_config
from cli.constants import (
    ATTRIBUTE_TIERS,
    CHECK_DIE_SIDES,
    RISK_THRESHOLDS,
    SKILL_TIERS,
)
from cli.errors import GlassError
from cli.local_env import load_repo_env
from cli.embeddings import EmbeddingBatch
from cli.main import main
from cli.messages import load_message_types
from cli.scene_beats import scene_close_note
from cli.state import load_state
from cli.validation import momentum_narrative_effect


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
    return {
        "GLASS_CONFIG": str(config),
        "GLASS_CAMPAIGN_ID": campaign_id,
        "GLASS_ROLE": "",
        "GLASS_TURN_ID": "",
        "AOG_PLAYER_SURFACE": "",
    }


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
            "--primary-drive",
            "care/protection" if character_id == "vel" else "curiosity",
            "--positive-trait",
            "Laughs at bad dock jokes and keeps a scorecard of the worst ones.",
            "--table-presence",
            "Starts a terrible joke scoreboard on the galley wall and invites edits.",
            "--non-work-want",
            "Wants to host a real birthday dinner where nobody talks about routes.",
            "--opening-social-action",
            "Hands Mara the first coffee and asks which joke gets retired tonight.",
            "--life-prompt",
            "what they do when praised=They redirect credit to the nearest apprentice and pour coffee.",
            "--life-prompt",
            "what they collect=They keep bent route tags sorted by harbor color.",
            "--pull-utilization",
            "Source: municipal ferry dispatch boards; Thesis: Vel turns public-route timing into hospitality, jokes, and urgent care, so every choice treats people as passengers to be welcomed rather than cases to process; Used in: archetype, drive, trait, table presence, non-work want, opening social action, item, skill, signature move, failure mode, voice.",
            "--skill",
            "spar reading=artisan",
            "--skill",
            "line work=apprentice",
            "--skill",
            "dock talk=apprentice",
        ],
        {**env, "GLASS_ROLE": f"player:{player}"},
    )


def arc_create_args(arc_id: str) -> list[str]:
    return [
        "arc",
        "create",
        arc_id,
        "--pull-source",
        "municipal elevator inspection logs",
        "--pull-utilization",
        "Inspection delay codes shape the first clock, gatehouse node, and permit clue.",
    ]


def _pass_rate(modifier: int, *, momentum: int, risk: str = "standard") -> float:
    target = RISK_THRESHOLDS[risk]
    passes = sum(
        1
        for die in range(1, CHECK_DIE_SIDES + 1)
        if die + modifier >= target
    )
    return passes / CHECK_DIE_SIDES


def _failure_rate(modifier: int, *, momentum: int, risk: str = "standard") -> float:
    return 1.0 - _pass_rate(modifier, momentum=momentum, risk=risk)


class GlassCliTests(unittest.TestCase):
    def test_standard_roll_probabilities_ignore_momentum(self) -> None:
        trained_standard = (
            SKILL_TIERS["apprentice"] + ATTRIBUTE_TIERS["standard"]
        )

        self.assertEqual(_failure_rate(trained_standard, momentum=0), 0.50)
        self.assertEqual(_failure_rate(trained_standard, momentum=3), 0.50)
        self.assertEqual(
            _failure_rate(SKILL_TIERS["fool"] + ATTRIBUTE_TIERS["standard"], momentum=0),
            0.70,
        )
        self.assertEqual(_failure_rate(trained_standard, momentum=-2), 0.50)
        self.assertEqual(
            _failure_rate(SKILL_TIERS["fool"] + ATTRIBUTE_TIERS["standard"], momentum=-2),
            0.70,
        )

    def test_roll_total_excludes_momentum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            create_test_character(runner, env, player="tev", character_id="vel")
            invoke_ok(runner, ["character", "set-momentum", "vel", "3"], player_env)

            with patch("cli.commands.roll.random.SystemRandom") as rng_factory:
                rng_factory.return_value.randint.side_effect = [1]
                rolled = invoke_ok(
                    runner,
                    [
                        "roll",
                        "spar reading",
                        "ingenuity",
                        "--risk",
                        "standard",
                        "--character",
                        "vel",
                    ],
                    player_env,
                )

            self.assertIn("total: 2", rolled.output)
            self.assertIn("outcome: collapse", rolled.output)
            self.assertIn("momentum_applied_to_total: false", rolled.output)

    def test_momentum_narrative_effect_thresholds(self) -> None:
        self.assertEqual(momentum_narrative_effect(3)[0], "additional_good")
        self.assertEqual(momentum_narrative_effect(2)[0], "none")
        self.assertEqual(momentum_narrative_effect(1)[0], "none")
        self.assertEqual(momentum_narrative_effect(0)[0], "additional_complication")
        self.assertEqual(momentum_narrative_effect(-2)[0], "additional_complication")

    def test_scene_close_note_frames_closure_as_available_not_overlong(self) -> None:
        self.assertIsNone(scene_close_note(5))
        self.assertEqual(
            scene_close_note(6),
            "this scene is entering landing range, not automatic closure; keep "
            "multiple active problem lanes live if the core tension has not "
            "landed.",
        )
        self.assertEqual(
            scene_close_note(8),
            "this scene has substantial resolved material; close or transition "
            "when the core tension lands unless a genuinely new scene question "
            "still belongs here.",
        )

    def test_character_goal_validation_requires_two_or_three_goals(self) -> None:
        self.assertEqual(_normalize_goals(("Find Rin.", "Pay the debt.")), [
            "Find Rin.",
            "Pay the debt.",
        ])
        with self.assertRaises(GlassError):
            _normalize_goals(("Only one.",))
        with self.assertRaises(GlassError):
            _normalize_goals(("one", "two", "three", "four"))

    def test_character_life_prompt_validation_requires_two_or_three_answers(self) -> None:
        answers = _normalize_life_prompt_answers(
            (
                "what they do when bored=They polish bent washers into counting tokens.",
                "what they do after a win=They buy breakfast for whoever stayed late.",
            )
        )

        self.assertEqual(answers[0]["prompt"], "what they do when bored")
        with self.assertRaises(GlassError):
            _normalize_life_prompt_answers(("what they do when bored=They pace.",))

    def test_character_pull_utilization_requires_identity_surfaces(self) -> None:
        note = (
            "Source: municipal ferry dispatch boards; Thesis: Vel turns public-route "
            "timing into hospitality, jokes, and urgent care, so every choice treats "
            "people as passengers to be welcomed rather than cases to process; Used "
            "in: archetype, drive, trait, table presence, non-work want, opening "
            "social action, item, skill, signature move, failure mode, voice."
        )

        self.assertEqual(_require_pull_utilization_note(note, "--pull-utilization"), note)
        with self.assertRaises(GlassError):
            _require_pull_utilization_note(
                "Source: municipal ferry dispatch boards; used in route skills.",
                "--pull-utilization",
            )

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
                "primary_drive": "care/protection",
                "positive_trait": "Laughs at bad dock jokes and keeps a scorecard.",
                "table_presence": "Runs the galley joke scoreboard between jobs.",
                "non_work_want": "Wants a birthday dinner where nobody discusses routes.",
                "opening_social_action": "Hands Mara coffee and asks which joke gets retired.",
                "life_prompt_answers": [
                    {
                        "prompt": "what they do when praised",
                        "answer": "They redirect credit to the nearest apprentice.",
                    },
                    {
                        "prompt": "what they collect",
                        "answer": "They keep bent route tags sorted by harbor color.",
                    },
                ],
                "pull_utilization_note": (
                    "Source: municipal ferry dispatch boards; Thesis: Vel turns route "
                    "timing into hospitality and urgent care; Used in: archetype, "
                    "drive, trait, table presence, non-work want, opening social "
                    "action, item, skill, signature move, failure mode, voice."
                ),
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
        self.assertIn("**Primary drive:** care/protection", body)
        self.assertIn("**Positive trait:** Laughs at bad dock jokes", body)
        self.assertIn("**Table presence:** Runs the galley joke scoreboard", body)
        self.assertIn("**Non-work want:** Wants a birthday dinner", body)
        self.assertIn("**Opening social action:** Hands Mara coffee", body)
        self.assertIn("## Life Prompt Answers", body)
        self.assertIn("## Non-Adjacent Pull Utilization", body)
        self.assertIn("- Get Mara safe passage.", body)
        self.assertIn("forged-route-seal", body)

    def test_signature_move_slots_progress_by_level(self) -> None:
        self.assertEqual(_signature_move_slots(1), 1)
        self.assertEqual(_signature_move_slots(2), 1)
        self.assertEqual(_signature_move_slots(3), 2)
        self.assertEqual(_signature_move_slots(5), 3)
        self.assertEqual(_signature_move_slots(9), 5)
        self.assertEqual(_signature_move_slots(10), 5)

    def test_skill_slot_cap_grows_with_level(self) -> None:
        self.assertEqual(_db.skill_slot_cap(1), 4)
        self.assertEqual(_db.skill_slot_cap(2), 5)
        self.assertEqual(_db.skill_slot_cap(5), 8)
        self.assertEqual(_db.skill_slot_cap(10), 13)

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

            duplicate_drive = runner.invoke(
                main,
                [
                    "character",
                    "bulk-update",
                    "--json",
                    json.dumps(
                        {
                            "character_id": "drova",
                            "set": {"primary_drive": "care/protection"},
                        }
                    ),
                ],
                env={**env, "GLASS_ROLE": "player:sumi"},
            )
            self.assertNotEqual(duplicate_drive.exit_code, 0)
            self.assertIn("primary drive already claimed", duplicate_drive.output)

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
                system_random.return_value.randint.side_effect = [10]
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

    def test_character_branch_messages_accept_character_recipient_alias(self) -> None:
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
                name="Drova Pell",
            )

            result = invoke_ok(
                runner,
                ["msg", "banter", "drova", "Hold", "the", "line."],
                {**env, "GLASS_ROLE": "player:tev", "AOG_PLAYER_SURFACE": "character"},
            )

            self.assertIn("recipient: drova", result.output)

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = env["GLASS_CONFIG"]
            try:
                with _db.connect(_db.load_pg_config(load_config())) as conn:
                    rows = _db.message_list(
                        conn,
                        campaign_id="c1",
                        agent_id="sumi",
                        limit=20,
                    )
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous

            self.assertEqual(rows[0]["recipient"], "sumi")
            self.assertEqual(rows[0]["sender"], "tev")

    def test_character_branch_message_reads_render_character_ids(self) -> None:
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
                name="Drova Pell",
            )
            invoke_ok(
                runner,
                ["msg", "banter", "drova", "Meet", "me", "below."],
                {**env, "GLASS_ROLE": "player:tev", "AOG_PLAYER_SURFACE": "character"},
            )

            result = invoke_ok(
                runner,
                ["msg", "read", "--since-checkpoint"],
                {**env, "GLASS_ROLE": "player:sumi", "AOG_PLAYER_SURFACE": "character"},
            )

            self.assertIn("sender: vel", result.output)
            self.assertIn("recipient: drova", result.output)

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

    def test_character_creation_mode_end_requires_relationship_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            campaign_root = tmp_path / "campaigns" / "c1"
            for player_id in ("kit", "renno", "sumi", "tev"):
                (campaign_root / "players" / player_id / "public").mkdir(
                    parents=True
                )

            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(
                runner,
                ["mode", "start", "character-creation", "character-creation"],
                dm_env,
            )

            blocked = runner.invoke(main, ["mode", "end"], env=dm_env)

            self.assertNotEqual(blocked.exit_code, 0)
            self.assertIn("relationship round is incomplete", blocked.output)
            self.assertIn(
                "kit: missing players/kit/public/relationships.md",
                blocked.output,
            )
            self.assertEqual(
                runtime_state(env)["mode_stack"][-1]["mode"],
                "character-creation",
            )

            for player_id in ("kit", "renno", "sumi", "tev"):
                (
                    campaign_root
                    / "players"
                    / player_id
                    / "public"
                    / "relationships.md"
                ).write_text(f"# {player_id} relationships\n", encoding="utf-8")

            ended = invoke_ok(runner, ["mode", "end"], dm_env)
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
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live problem for the party.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-problem",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Frame the first problem",
                    "--question",
                    "What immediate pressure is now live for the party?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "dm",
                    "--role",
                    "dm",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play-dm",
                    "--no-turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            turn_file = tmp_path / "turn.md"
            turn_file.write_text("Mara frames the scene.", encoding="utf-8")
            end_file = tmp_path / "turn-closeout.json"
            invoke_ok(runner, ["beat", "check"], dm_env)
            invoke_ok(runner, ["turn", "audit"], dm_env)
            ended = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Mara frames the opening choice.",
                    "--state",
                    "table unchanged",
                    "--rolls",
                    "none",
                    "--next",
                    "default",
                ],
                {**dm_env, "AOG_TURN_CLOSEOUT": str(end_file)},
            )
            self.assertIn("summary: \"Mara frames the opening choice.\"", ended.output)
            self.assertIn("valid: true", ended.output)
            self.assertTrue(end_file.exists())

            appended = invoke_ok(
                runner,
                ["turn", "append", str(turn_file), "--speaker", "dm"],
                dm_env,
            )
            self.assertIn("turn_id: 1", appended.output)
            self.assertIn("turn_summary: \"Mara frames the opening choice.\"", appended.output)
            self.assertIn("transcript_export_path:", appended.output)

            found = invoke_ok(runner, ["turns", "find", "--limit", "1"], dm_env)
            self.assertIn("Mara frames the scene.", found.output)
            text_found = invoke_ok(
                runner,
                ["turns", "find", "--text", "opening choice", "--limit", "1"],
                dm_env,
            )
            self.assertIn("Mara frames the opening choice.", text_found.output)

            feed = invoke_ok(runner, ["turns", "feed", "--after-turn", "0"], dm_env)
            self.assertIn("event_type: turn.committed", feed.output)
            self.assertIn('prose: "Mara frames the scene."', feed.output)
            self.assertIn('summary: "Mara frames the opening choice."', feed.output)

            transcript = (tmp_path / "campaigns" / "c1" / "transcript.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Turn 1 - dm (dm) - scene-play, opening", transcript)
            self.assertIn("Mara frames the scene.", transcript)

    def test_turn_end_reports_invalid_player_turn_type_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev decide to do with the opening pressure?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["beat", "check"], player_env)
            invoke_ok(runner, ["turn", "audit"], player_env)

            invalid = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Tev hesitates.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                    "--next",
                    "default",
                ],
                player_env,
            )
            self.assertIn("valid: false", invalid.output)
            self.assertIn("problems:", invalid.output)
            self.assertIn("`--turn-type` is required", invalid.output)

            valid = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Tev taps the rail once and yields the beat.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                    "--turn-type",
                    "pass",
                    "--next",
                    "default",
                ],
                player_env,
            )
            self.assertIn("valid: true", valid.output)
            self.assertIn("turn_type: pass", valid.output)

    def test_turn_end_requires_turn_audit_before_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev do with the opening pressure?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["beat", "check"], player_env)
            ended = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Tev yields for a beat.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                    "--turn-type",
                    "pass",
                ],
                player_env,
            )
            self.assertIn("valid: false", ended.output)
            self.assertIn("run `glass turn audit` before `glass turn end`", ended.output)

    def test_turn_audit_reports_and_clears_soft_and_hard_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev do with the opening pressure?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )

            first_audit = invoke_ok(runner, ["turn", "audit"], player_env)
            self.assertIn("ready_for_turn_end: false", first_audit.output)
            self.assertIn("You MUST still run glass beat check.", first_audit.output)
            self.assertIn(
                "You sent 0 messages this turn; consider sending something.",
                first_audit.output,
            )
            self.assertIn(
                "You ran 0 recall/search checks this turn; consider checking the available surfaces if you are uncertain.",
                first_audit.output,
            )
            self.assertIn(
                "You recorded 0 durable state updates this turn; if the turn changed canon or table state, commit it before closing.",
                first_audit.output,
            )

            invoke_ok(runner, ["beat", "check"], player_env)
            invoke_ok(
                runner,
                ["msg", "send", "banter", "dm", "Tev asks Mara to hold the next reveal for one beat."],
                player_env,
            )
            second_audit = invoke_ok(runner, ["turn", "audit"], player_env)
            self.assertIn("ready_for_turn_end: true", second_audit.output)
            self.assertIn("soft_considerations: []", second_audit.output)
            self.assertIn("hard_requirements: []", second_audit.output)
            self.assertNotIn("You MUST still run glass beat check.", second_audit.output)
            self.assertNotIn(
                "You sent 0 messages this turn; consider sending something.",
                second_audit.output,
            )

    def test_facade_check_and_done_cover_turn_start_and_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev do with the opening pressure?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                ["msg", "banter", "party", "Mara wants Tev to take the first clear line."],
                dm_env,
            )
            invoke_ok(
                runner,
                ["clock", "set", "dm-only-pressure", "--max", "4"],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )

            checked = invoke_ok(runner, ["check"], player_env)
            self.assertIn("unread_message_count: 1", checked.output)
            self.assertIn("beat_check_marked: true", checked.output)
            self.assertIn("ready_for_done: true", checked.output)
            self.assertNotIn("dm-only-pressure", checked.output)

            ended = invoke_ok(
                runner,
                [
                    "done",
                    "--summary",
                    "Tev yields for Pell to answer the visible problem.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                    "--type",
                    "pass",
                ],
                player_env,
            )
            self.assertIn("valid: true", ended.output)
            self.assertIn("hard_requirements: []", ended.output)

    def test_facade_next_wraps_handoff_and_dm_round_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            handoff = invoke_ok(runner, ["next", "handoff", "dm"], player_env)
            self.assertIn("agent: dm", handoff.output)

            rapid = invoke_ok(
                runner,
                ["next", "rapid-round", "--players", "tev,sumi", "react to the flare"],
                dm_env,
            )
            self.assertIn('rapid_prompt: "react to the flare"', rapid.output)

            state = runtime_state(env)
            self.assertEqual(state["next_speakers"][0]["agent"], "dm")
            self.assertEqual(state["next_speakers"][1]["agent"], "tev")
            self.assertEqual(state["next_speakers"][1]["rapid_prompt"], "react to the flare")
            self.assertEqual(state["next_speakers"][2]["agent"], "sumi")

    def test_prelude_turn_end_requires_scene_contract_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "prelude", "prelude"], dm_env)
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "dm",
                    "--role",
                    "dm",
                    "--mode",
                    "prelude",
                    "--scene",
                    "prelude",
                    "--kind",
                    "prelude",
                    "--no-turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["mode", "start", "scene-play", "prelude-opening"], dm_env)

            first_audit = invoke_ok(runner, ["turn", "audit"], dm_env)
            self.assertIn("ready_for_turn_end: false", first_audit.output)
            self.assertIn("You MUST still run glass beat check.", first_audit.output)
            self.assertIn("This active scene has 0 scene clocks.", first_audit.output)
            self.assertIn("This active scene has 0 active beats.", first_audit.output)

            invalid = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Prelude opening staged.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                ],
                dm_env,
            )
            self.assertIn("valid: false", invalid.output)
            self.assertIn("You MUST still run glass beat check.", invalid.output)
            self.assertIn(
                "the active scene has 0 scene clocks; the DM must declare one before active play can continue.",
                invalid.output,
            )
            self.assertIn(
                "the active scene has 0 active beats; start one before active play can continue.",
                invalid.output,
            )

            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the prelude scene",
                    "--goal",
                    "Land the first visible prelude decision.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Open the first choice",
                    "--question",
                    "What does the crew do first?",
                ],
                dm_env,
            )
            invoke_ok(runner, ["beat", "check"], dm_env)
            second_audit = invoke_ok(runner, ["turn", "audit"], dm_env)
            self.assertIn("ready_for_turn_end: true", second_audit.output)
            self.assertIn("hard_requirements: []", second_audit.output)

            valid = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Prelude opening staged.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                ],
                dm_env,
            )
            self.assertIn("valid: true", valid.output)

    def test_turn_audit_allows_scene_closing_after_last_beat_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "1",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev do with the opening pressure?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["beat", "check"], player_env)
            invoke_ok(
                runner,
                [
                    "beat",
                    "close",
                    "first-decision",
                    "--outcome",
                    "Tev resolves the opening lane call.",
                    "--clock-delta",
                    "1",
                ],
                player_env,
            )
            audit = invoke_ok(runner, ["turn", "audit"], player_env)
            self.assertIn("ready_for_turn_end: true", audit.output)
            self.assertNotIn("This active scene has 0 scene clocks.", audit.output)
            self.assertNotIn("This active scene has 0 active beats.", audit.output)
            self.assertIn("This scene has 0 active scene clocks.", audit.output)
            self.assertIn("This scene has 0 active beats.", audit.output)
            self.assertIn("end with `--next dm`", audit.output)

            ended = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Tev resolves the opening lane call and leaves the scene ready to close.",
                    "--state",
                    "Closed beat first-decision and resolved opening-contract 1/1.",
                    "--rolls",
                    "none",
                    "--turn-type",
                    "act",
                    "--scene-status",
                    "closing",
                ],
                player_env,
            )
            self.assertIn("valid: true", ended.output)

    def test_scene_clock_polarity_groups_and_direct_tick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)

            declared = invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "alarm",
                    "--label",
                    "Alarm spreads",
                    "--goal",
                    "The cutters wake the quay patrols.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                    "--polarity",
                    "threat",
                ],
                dm_env,
            )
            self.assertIn("polarity: threat", declared.output)

            checked = invoke_ok(runner, ["check"], dm_env)
            self.assertIn("clock_groups:", checked.output)
            self.assertIn("threat:", checked.output)
            self.assertIn("This scene has no active objective clock", checked.output)

            ticked = invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "tick",
                    "alarm",
                    "2",
                    "--outcome",
                    "The cutter flare catches the patrol mirror.",
                ],
                dm_env,
            )
            self.assertIn("before: 0", ticked.output)
            self.assertIn("after: 2", ticked.output)
            self.assertIn("delta: 2", ticked.output)

    def test_failed_roll_requires_visible_consequence_at_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            create_test_character(runner, env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                    "--polarity",
                    "objective",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev do with the opening pressure?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--character",
                    "vel",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["check"], player_env)
            with patch("cli.commands.roll.random.SystemRandom") as rng_factory:
                rng_factory.return_value.randint.side_effect = [1]
                rolled = invoke_ok(
                    runner,
                    [
                        "roll",
                        "spar reading",
                        "ingenuity",
                        "--risk",
                        "desperate",
                        "--character",
                        "vel",
                    ],
                    player_env,
                )
            self.assertIn("outcome: collapse", rolled.output)

            invalid = invoke_ok(
                runner,
                [
                    "done",
                    "--summary",
                    "Vel tests the spar and loses footing.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "spar reading collapse",
                    "--turn-type",
                    "act",
                ],
                player_env,
            )
            self.assertIn("valid: false", invalid.output)
            self.assertIn("roll needs a consequence", invalid.output)

            valid = invoke_ok(
                runner,
                [
                    "done",
                    "--summary",
                    "Vel tests the spar and loses footing.",
                    "--state",
                    "The spar snaps; Vel is hanging below the gangway.",
                    "--rolls",
                    "spar reading collapse",
                    "--turn-type",
                    "act",
                ],
                player_env,
            )
            self.assertIn("valid: true", valid.output)

    def test_turn_audit_pushes_pass_guidance_after_many_completed_beats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Keep the scene's live question visible.",
                    "--value",
                    "0",
                    "--max",
                    "20",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            for index in range(9):
                beat_id = f"resolved-beat-{index}"
                invoke_ok(
                    runner,
                    [
                        "beat",
                        "start",
                        beat_id,
                        "--clock",
                        "opening-contract",
                        "--label",
                        f"Resolved beat {index}",
                        "--question",
                        f"What resolves beat {index}?",
                    ],
                    dm_env,
                )
                invoke_ok(
                    runner,
                    [
                        "beat",
                        "close",
                        beat_id,
                        "--outcome",
                        f"Beat {index} resolves.",
                    ],
                    dm_env,
                )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["beat", "check"], player_env)

            audit = invoke_ok(runner, ["turn", "audit"], player_env)

            self.assertIn("ready_for_turn_end: true", audit.output)
            self.assertIn("This scene already has 9 completed beats.", audit.output)
            self.assertIn("closed beats and 0 scene clock movements", audit.output)
            self.assertIn("`--turn-type pass`", audit.output)
            self.assertIn("`--next dm`", audit.output)

    def test_beat_check_allows_recovery_after_last_beat_already_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "1",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev do with the opening pressure?",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )

            invoke_ok(
                runner,
                [
                    "beat",
                    "close",
                    "first-decision",
                    "--outcome",
                    "Tev resolves the opening lane call.",
                    "--clock-delta",
                    "1",
                ],
                player_env,
            )

            checked = invoke_ok(runner, ["beat", "check"], player_env)
            self.assertIn("required: true", checked.output)
            self.assertIn("clock_count: 0", checked.output)
            self.assertIn("active_beats: []", checked.output)

            audit = invoke_ok(runner, ["turn", "audit"], player_env)
            self.assertIn("ready_for_turn_end: true", audit.output)
            self.assertIn("hard_requirements: []", audit.output)

    def test_dm_turn_end_rejects_open_arc_with_no_active_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, arc_create_args("borrowed-wall"), dm_env)
            invoke_ok(runner, ["arc", "activate", "borrowed-wall"], dm_env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "dm",
                    "--role",
                    "dm",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play-dm",
                    "--no-turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["mode", "end"], dm_env)

            audit = invoke_ok(runner, ["turn", "audit"], dm_env)
            self.assertIn("ready_for_turn_end: false", audit.output)
            self.assertIn(
                "No active mode is staged while active arc `borrowed-wall` remains open.",
                audit.output,
            )

            ended = invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Scene closed but no next mode is staged.",
                    "--state",
                    "Closed the scene.",
                    "--rolls",
                    "none",
                    "--scene-status",
                    "ended",
                    "--next",
                    "dm",
                ],
                dm_env,
            )
            self.assertIn("valid: false", ended.output)
            self.assertIn(
                "No active mode is staged while active arc `borrowed-wall` remains open.",
                ended.output,
            )

    def test_scene_beats_skip_pass_turns_and_age_on_non_pass_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            player_env = {**env, "GLASS_ROLE": "player:tev"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "scene-play", "opening"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "opening-contract",
                    "--label",
                    "Open the scene",
                    "--goal",
                    "Land the first live player decision.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-decision",
                    "--clock",
                    "opening-contract",
                    "--label",
                    "Make the first call",
                    "--question",
                    "What does Tev do with the opening pressure?",
                ],
                dm_env,
            )

            pass_turn = tmp_path / "pass-turn.md"
            pass_turn.write_text("Tev yields the floor for a moment.", encoding="utf-8")
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "tev",
                    "--role",
                    "player",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play",
                    "--turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["beat", "check"], player_env)
            invoke_ok(runner, ["turn", "audit"], player_env)
            invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Tev yields the beat for a moment.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                    "--turn-type",
                    "pass",
                ],
                player_env,
            )
            invoke_ok(runner, ["turn", "append", str(pass_turn), "--speaker", "tev"], player_env)

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = env["GLASS_CONFIG"]
            try:
                with _db.connect(_db.load_pg_config(load_config())) as conn:
                    beat = _db.scene_beat_get(
                        conn,
                        campaign_id="c1",
                        scene_id="opening",
                        beat_id="first-decision",
                    )
                self.assertEqual(beat["non_pass_turns"], 0)
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous

            action_turn = tmp_path / "action-turn.md"
            action_turn.write_text("Mara forces the question back onto the table.", encoding="utf-8")
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0002",
                    "--actor",
                    "dm",
                    "--role",
                    "dm",
                    "--mode",
                    "scene-play",
                    "--scene",
                    "opening",
                    "--kind",
                    "active-play-dm",
                    "--no-turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["beat", "check"], dm_env)
            invoke_ok(runner, ["turn", "audit"], dm_env)
            invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Mara forces the question back onto the table.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                ],
                dm_env,
            )
            invoke_ok(runner, ["turn", "append", str(action_turn), "--speaker", "dm"], dm_env)

            previous = os.environ.get("GLASS_CONFIG")
            os.environ["GLASS_CONFIG"] = env["GLASS_CONFIG"]
            try:
                with _db.connect(_db.load_pg_config(load_config())) as conn:
                    beat = _db.scene_beat_get(
                        conn,
                        campaign_id="c1",
                        scene_id="opening",
                        beat_id="first-decision",
                    )
                self.assertEqual(beat["non_pass_turns"], 1)
            finally:
                if previous is None:
                    os.environ.pop("GLASS_CONFIG", None)
                else:
                    os.environ["GLASS_CONFIG"] = previous

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
            invoke_ok(runner, arc_create_args("opening"), dm_env)
            with runner.isolated_filesystem(temp_dir=tmp_path):
                (Path("dm") / "workspace").mkdir(parents=True)
                (Path("dm") / "workspace" / "sync-note.md").write_text(
                    "DM note from projected workspace.\n",
                    encoding="utf-8",
                )
                (Path("table")).mkdir()
                (Path("table") / "visible-artifact.md").write_text(
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
                (root / "table" / "visible-artifact.md").read_text(encoding="utf-8"),
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
            self.assertIn("table/visible-artifact.md", indexed.output)

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
                    json.dumps({"files": {"table/visible-artifact.md": "old-hash"}}),
                    encoding="utf-8",
                )
                Path(".glass-projection-manifest.json").chmod(0o440)
                Path("table").mkdir()
                (Path("table") / "visible-artifact.md").write_text(
                    "stale projected edit\n",
                    encoding="utf-8",
                )
                with patch("cli.embeddings.embed_text", return_value=fake_embedding):
                    invoke_ok(
                        runner,
                        [
                            "table",
                            "write",
                            "table/visible-artifact.md",
                            "--body",
                            "canonical table\n",
                        ],
                        dm_env,
                    )

                self.assertEqual(
                    (Path("table") / "visible-artifact.md").read_text(encoding="utf-8"),
                    "canonical table\n",
                )
                manifest = json.loads(
                    Path(".glass-projection-manifest.json").read_text(encoding="utf-8")
                )
                self.assertNotEqual(
                    manifest["files"]["table/visible-artifact.md"],
                    "old-hash",
                )

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
                    [
                        "scene",
                        "clock",
                        "declare",
                        "opening-contract",
                        "--label",
                        "Open the scene",
                        "--goal",
                        "Move the scene through two public turns.",
                        "--value",
                        "0",
                        "--max",
                        "4",
                        "--direction",
                        "progress",
                    ],
                    dm_env,
                )
                invoke_ok(
                    runner,
                    [
                        "beat",
                        "start",
                        "first-problem",
                        "--clock",
                        "opening-contract",
                        "--label",
                        "Open the problem",
                        "--question",
                        "What immediate pressure is visible at the gate?",
                    ],
                    dm_env,
                )
                invoke_ok(
                    runner,
                    [
                        "turn",
                        "begin",
                        "--turn-id",
                        "c1-t0001",
                        "--actor",
                        "dm",
                        "--role",
                        "dm",
                        "--mode",
                        "scene-play",
                        "--scene",
                        "opening",
                        "--kind",
                        "active-play-dm",
                        "--no-turn-type-required",
                        "--disallow-player-scene-close",
                    ],
                    env,
                )
                invoke_ok(runner, ["beat", "check"], dm_env)
                invoke_ok(runner, ["turn", "audit"], dm_env)
                invoke_ok(
                    runner,
                    [
                        "turn",
                        "end",
                        "--summary",
                        "The castle gate opens for the party.",
                        "--state",
                        "no state change",
                        "--rolls",
                        "none",
                    ],
                    dm_env,
                )
                invoke_ok(
                    runner,
                    ["turn", "append", str(castle_turn), "--speaker", "dm"],
                    dm_env,
                )
                invoke_ok(
                    runner,
                    [
                        "turn",
                        "begin",
                        "--turn-id",
                        "c1-t0002",
                        "--actor",
                        "dm",
                        "--role",
                        "dm",
                        "--mode",
                        "scene-play",
                        "--scene",
                        "opening",
                        "--kind",
                        "active-play-dm",
                        "--no-turn-type-required",
                        "--disallow-player-scene-close",
                    ],
                    env,
                )
                invoke_ok(runner, ["beat", "check"], dm_env)
                invoke_ok(runner, ["turn", "audit"], dm_env)
                invoke_ok(
                    runner,
                    [
                        "turn",
                        "end",
                        "--summary",
                        "The river barge slips into fog.",
                        "--state",
                        "no state change",
                        "--rolls",
                        "none",
                    ],
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

    def test_turn_initiative_auto_includes_dm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, ["mode", "start", "action", "ambush"], dm_env)

            invoke_ok(
                runner,
                ["turn", "initiative", "--participants", "tev,kit"],
                dm_env,
            )

            state = runtime_state(env)
            action_order = state["action_order"]
            self.assertEqual(set(action_order["order"]), {"tev", "dm", "kit"})
            self.assertEqual(len(action_order["rolls"]), 3)

    def test_arc_activate_switches_current_arc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            invoke_ok(runner, arc_create_args("main-opening"), dm_env)
            invoke_ok(runner, arc_create_args("prelude"), dm_env)
            current = invoke_ok(runner, ["arc", "current"], dm_env)
            self.assertIn("prelude", current.output)

            activated = invoke_ok(runner, ["arc", "activate", "main-opening"], dm_env)

            self.assertIn("main-opening", activated.output)
            state = runtime_state(env)
            self.assertEqual(state["active_arc"], "main-opening")

    def test_arc_close_check_reports_scene_and_clock_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, arc_create_args("first-arc"), dm_env)
            invoke_ok(
                runner,
                ["scene", "create", "opening", "--type", "scene-play"],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "clock",
                    "set",
                    "harm-spreads",
                    "--scope",
                    "arc",
                    "--anchor",
                    "first-arc",
                    "--max",
                    "4",
                ],
                dm_env,
            )

            result = invoke_ok(runner, ["arc", "close-check", "first-arc"], dm_env)

            self.assertIn("ready_to_close: false", result.output)
            self.assertIn("active scene `opening` is still open", result.output)
            self.assertIn("resolve or archive active arc clocks: harm-spreads", result.output)
            self.assertIn("choose:", result.output)
            self.assertIn("- close", result.output)

    def test_campaign_pull_note_records_required_utilization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)

            result = invoke_ok(
                runner,
                [
                    "campaign",
                    "pull-note",
                    "--source",
                    "city water-main repair tickets",
                    "--used-in",
                    "campaign scarcity",
                    "--note",
                    "Valve-tag replacement delays shape the rationing scarcity and first faction dispute.",
                ],
                dm_env,
            )

            self.assertIn("campaign_id: c1", result.output)
            note = (
                tmp_path
                / "campaigns"
                / "c1"
                / "dm"
                / "notes"
                / "pulls"
                / "campaign-non-adjacent.md"
            ).read_text(encoding="utf-8")
            self.assertIn("city water-main repair tickets", note)
            self.assertIn("Valve-tag replacement delays", note)

    def test_scene_create_accepts_custom_type_and_trackers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runner = CliRunner()
            env = make_env(tmp_path)
            dm_env = {**env, "GLASS_ROLE": "dm"}
            invoke_ok(runner, ["session", "new", "--campaign", "c1"], env)
            invoke_ok(runner, arc_create_args("first-arc"), dm_env)

            scene = invoke_ok(
                runner,
                ["scene", "create", "duke-gate", "--type", "courtroom-standoff"],
                dm_env,
            )
            self.assertIn("scene_type: courtroom-standoff", scene.output)
            root = tmp_path / "campaigns" / "c1"
            table_root = root / "table"
            self.assertFalse((table_root / "index.md").exists())
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

            retired = runner.invoke(
                main,
                ["table", "write", "index.md", "--body", "not allowed"],
                env=dm_env,
            )
            self.assertNotEqual(retired.exit_code, 0)
            self.assertIn("table/index.md is retired", retired.output)

            lore_source = root / "shared" / "lore" / "ships" / "splitfork.md"
            lore_source.parent.mkdir(parents=True)
            lore_source.write_text("# The Splitfork\n\nVisible ship lore.\n", encoding="utf-8")
            fake_embedding = EmbeddingBatch(
                vectors=[[1.0] + [0.0] * 767],
                model="test-embedding",
                provider="test",
                dimensions=768,
            )
            with (
                patch("cli.embeddings.embed_text", return_value=fake_embedding),
                patch(
                    "cli.commands.entity._mirror_entity_to_graph",
                    return_value={"status": "mocked"},
                ),
            ):
                used = invoke_ok(
                    runner,
                    [
                        "table",
                        "use",
                        "shared/lore/ships/splitfork.md",
                        "--as",
                        "splitfork.md",
                    ],
                    dm_env,
                )
                self.assertIn("table/splitfork.md", used.output)
                promoted = invoke_ok(
                    runner,
                    [
                        "lore",
                        "promote",
                        "table/splitfork.md",
                        "--to",
                        "ships/splitfork-copy.md",
                    ],
                    dm_env,
                )
            self.assertIn("shared/lore/ships/splitfork-copy.md", promoted.output)
            self.assertEqual(
                (root / "table" / "splitfork.md").read_text(encoding="utf-8"),
                "# The Splitfork\n\nVisible ship lore.\n",
            )
            self.assertTrue(
                (root / "shared" / "lore" / "ships" / "splitfork-copy.md").exists()
            )

            invoke_ok(runner, ["mode", "start", "action", "duke-gate"], dm_env)
            invoke_ok(
                runner,
                [
                    "scene",
                    "clock",
                    "declare",
                    "gate-access",
                    "--label",
                    "Gain gate access",
                    "--goal",
                    "Open the duke's gate without losing leverage.",
                    "--value",
                    "0",
                    "--max",
                    "4",
                    "--direction",
                    "progress",
                ],
                dm_env,
            )
            invoke_ok(
                runner,
                [
                    "beat",
                    "start",
                    "first-push",
                    "--clock",
                    "gate-access",
                    "--label",
                    "Push the gate",
                    "--question",
                    "Can the party force a way through the duke's gate?",
                ],
                dm_env,
            )
            turn_file = tmp_path / "scene-turn.md"
            turn_file.write_text("Mara points to the castle gate.", encoding="utf-8")
            invoke_ok(
                runner,
                [
                    "turn",
                    "begin",
                    "--turn-id",
                    "c1-t0001",
                    "--actor",
                    "dm",
                    "--role",
                    "dm",
                    "--mode",
                    "action",
                    "--scene",
                    "duke-gate",
                    "--kind",
                    "active-play-dm",
                    "--no-turn-type-required",
                    "--disallow-player-scene-close",
                ],
                env,
            )
            invoke_ok(runner, ["beat", "check"], dm_env)
            invoke_ok(runner, ["turn", "audit"], dm_env)
            invoke_ok(
                runner,
                [
                    "turn",
                    "end",
                    "--summary",
                    "Mara points the party at the castle gate.",
                    "--state",
                    "no state change",
                    "--rolls",
                    "none",
                ],
                dm_env,
            )
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
            invoke_ok(runner, arc_create_args("first-arc"), dm_env)
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

            arc = invoke_ok(runner, arc_create_args("first-arc"), dm_env)
            self.assertIn("arc_id: first-arc", arc.output)
            pull_note = (
                tmp_path / "campaigns" / "c1" / "arcs" / "first-arc" / "pulls.md"
            ).read_text(encoding="utf-8")
            self.assertIn("municipal elevator inspection logs", pull_note)

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
                    "warrant-clock.md",
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
            self.assertTrue((archived_table / "warrant-clock.md").exists())
            self.assertIn(
                "The warrant clock is visible",
                (archived_table / "warrant-clock.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "No scene is currently active",
                (root / "table" / "scene.md").read_text(encoding="utf-8"),
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
