import unittest
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cli.api_client import should_proxy
from cli.api_grants import mint_grant
from cli import mcp_server


class GlassMcpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patcher = patch.dict(os.environ, {"GLASS_ROLE": "dm"}, clear=False)
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()

    def test_mcp_tools_do_not_expose_generic_argv_escape_hatch(self) -> None:
        tool_names = set(mcp_server.mcp._tool_manager._tools)

        self.assertIn("glass_state_update", tool_names)
        self.assertIn("glass_done", tool_names)
        self.assertIn("glass_turn_append", tool_names)
        self.assertIn("glass_roll", tool_names)
        self.assertIn("glass_scene_transition", tool_names)
        self.assertIn("glass_scene_pressure", tool_names)
        self.assertIn("glass_beat_start", tool_names)
        self.assertIn("glass_turn_handoff", tool_names)
        self.assertIn("glass_clock_set", tool_names)
        self.assertIn("glass_scene_tracker_set", tool_names)
        self.assertIn("glass_scene_tracker_tick", tool_names)
        self.assertIn("glass_scene_tracker_list", tool_names)
        self.assertNotIn("glass_tool_list", tool_names)
        self.assertNotIn("glass_command", tool_names)

    def test_mcp_help_mapping_covers_registered_state_tools(self) -> None:
        tool_names = set(mcp_server.mcp._tool_manager._tools)

        self.assertEqual(
            tool_names - {"glass_help"},
            set(mcp_server._MCP_HELP_ARGS),
        )

    def test_mcp_response_instructions_cover_registered_tools(self) -> None:
        tool_names = set(mcp_server.mcp._tool_manager._tools)

        self.assertEqual(tool_names, set(mcp_server._MCP_RESPONSE_INSTRUCTIONS))
        for tool_name, instructions in mcp_server._MCP_RESPONSE_INSTRUCTIONS.items():
            with self.subTest(tool=tool_name):
                self.assertIsInstance(instructions, list)
                self.assertGreaterEqual(len(instructions), 1)
                self.assertTrue(all(isinstance(item, str) and item for item in instructions))
                response = mcp_server._run_service(
                    lambda: {"status": "ok"},
                    tool_name=tool_name,
                )
                self.assertTrue(response["ok"])
                self.assertIn("instructions", response)
                self.assertGreaterEqual(len(response["instructions"]), 1)

    def test_run_service_adds_instructional_success_and_error_responses(self) -> None:
        success = mcp_server._run_service(
            lambda: {"valid": True},
            tool_name="glass_done",
        )

        self.assertTrue(success["ok"])
        self.assertIn("instructions", success)
        self.assertEqual(
            success["instructions"],
            [
                'Closeout is valid. Now call glass_turn_append(body="<public prose>") and then stop this invocation.'
            ],
        )
        self.assertIn("instructions:", success["output"])

        failure = mcp_server._run_service(
            lambda: (_ for _ in ()).throw(mcp_server.GlassError("bad input")),
            tool_name="glass_done",
        )

        self.assertFalse(failure["ok"])
        self.assertIn("instructions", failure)
        self.assertIn("Do not work around this failed tool call", failure["instructions"][0])
        self.assertIn('glass_help(command="glass_done")', failure["instructions"][1])

    def test_low_importance_fact_updates_warn_without_rejection(self) -> None:
        response = mcp_server._run_service(
            lambda: {
                "count": 1,
                "facts": {
                    "facts": [
                        {
                            "subject_id": "tev",
                            "predicate": "habit",
                            "importance": "low",
                        }
                    ]
                },
                "inventory": [],
                "importance_warnings": [
                    "Low/minor facts were stored but are omitted from fact-pack output."
                ],
            },
            tool_name="glass_state_update",
        )

        self.assertTrue(response["ok"])
        self.assertIn("Low/minor facts were stored", response["instructions"][0])
        self.assertIn("State updates are stored", " ".join(response["instructions"]))

    def test_done_instructions_surface_only_low_minor_fact_warning(self) -> None:
        response = mcp_server._run_service(
            lambda: {
                "valid": True,
                "soft_considerations": [
                    "Only low/minor facts were added this turn. They are stored for audit/debug but omitted from fact-pack output; add a high or medium fact if playable state changed."
                ],
            },
            tool_name="glass_done",
        )

        self.assertTrue(response["ok"])
        self.assertIn("Only low/minor facts", response["instructions"][0])
        self.assertIn("fact set is weak", response["instructions"][1])

    def test_scene_board_mutation_responses_remind_agents_to_recheck(self) -> None:
        scene_board_tools = {
            "glass_mode_end",
            "glass_mode_start",
            "glass_scene_create",
            "glass_scene_end",
            "glass_scene_transition",
            "glass_scene_clock_declare",
            "glass_scene_clock_tick",
            "glass_scene_tracker_set",
            "glass_scene_tracker_tick",
            "glass_scene_pressure",
            "glass_beat_start",
            "glass_beat_close",
            "glass_beat_convert",
            "glass_turn_initiative",
        }

        for tool_name in sorted(scene_board_tools):
            with self.subTest(tool=tool_name):
                instructions = " ".join(mcp_server._MCP_RESPONSE_INSTRUCTIONS[tool_name])
                self.assertIn("glass_check()", instructions)
                self.assertIn("glass_done", instructions)

        state_update_instructions = " ".join(
            mcp_server._MCP_RESPONSE_INSTRUCTIONS["glass_state_update"]
        )
        self.assertIn("after the last glass_check()", state_update_instructions)
        self.assertIn("before glass_done", state_update_instructions)

    def test_state_update_examples_are_object_shaped(self) -> None:
        root = Path(__file__).resolve().parents[1]
        paths = [
            *(root / "templates").rglob("*.md"),
            *(root / "docs").rglob("*.md"),
            *(root / "src").rglob("*.py"),
        ]
        forbidden = [
            "glass_state_update(updates=[...])",
            'glass_state_update(updates=[{"kind": "fact", ...}])',
            '{"kind": "fact", ...}',
            '{"kind": "inventory_add", ...}',
            '{"kind": "inventory_remove", ...}',
            '"subject_id": "...", "predicate": "...", "text": "..."',
        ]

        offenders: list[str] = []
        fact_importance_offenders: list[str] = []
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                if pattern in text:
                    offenders.append(f"{path.relative_to(root)} contains {pattern}")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if '"kind": "fact"' in line and '"importance"' not in line:
                    fact_importance_offenders.append(
                        f"{path.relative_to(root)}:{line_number} fact example omits importance"
                    )

        self.assertEqual(offenders, [])
        self.assertEqual(fact_importance_offenders, [])

    def test_mcp_help_accepts_mcp_tool_names_and_normalizes_subcommands(self) -> None:
        results = [
            mcp_server.glass_help(command="glass_state_update"),
            mcp_server.glass_help(command="character", subcommand="inventory_add"),
            mcp_server.glass_help(command="glass_scene_clock_declare"),
            mcp_server.glass_help(command="glass_done"),
        ]

        self.assertTrue(all(result["ok"] for result in results))
        self.assertIn("glass_state_update", results[0]["output"])
        self.assertIn("glass_state_update", results[1]["output"])
        self.assertIn("glass_scene_clock_declare", results[2]["output"])
        self.assertIn("glass_done", results[3]["output"])
        self.assertIn("input_schema", results[0]["output"])

    def test_mcp_server_has_no_command_executor_path(self) -> None:
        source = Path(mcp_server.__file__).read_text(encoding="utf-8")

        self.assertNotIn("invoke_current_turn_args", source)
        self.assertNotIn("_run_glass", source)
        self.assertNotIn("command_executor", source)

    def test_mcp_main_loads_repo_env_before_serving_stdio(self) -> None:
        with (
            patch("cli.mcp_server.load_repo_env") as load_env,
            patch.object(mcp_server.mcp, "run") as run_server,
        ):
            mcp_server.main([])

        load_env.assert_called_once_with()
        run_server.assert_called_once_with(transport="stdio")

    def test_mcp_mutation_rejects_operator_during_active_turn(self) -> None:
        with (
            patch("cli.mcp_server.current_role") as current_role,
            patch("cli.mcp_server.get_paths", return_value=object()),
            patch("cli.mcp_server.active_campaign_id", return_value="c1"),
            patch("cli.mcp_server.load_state", return_value={"active_turn_id": "turn-1"}),
            patch("cli.mcp_server._state_update_service") as service,
        ):
            current_role.return_value = type("Role", (), {"kind": "operator"})()
            result = mcp_server.glass_state_update(
                updates=[
                    {
                        "kind": "fact",
                        "subject_id": "gate",
                        "predicate": "status",
                        "text": "Gate is closed.",
                        "audience": "continuity",
                        "importance": "medium",
                    }
                ],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], 77)
        self.assertIn("MCP mutation has no turn actor", result["output"])
        service.assert_not_called()

    def test_mcp_state_update_batches_facts_and_inventory(self) -> None:
        with patch(
            "cli.mcp_server._state_update_service",
            return_value={"count": 3},
        ) as service:
            updates = [
                {
                    "kind": "fact",
                    "subject_id": "tev",
                    "predicate": "relationship",
                    "object_id": "sumi",
                    "text": "Tev owes Sumi a clean route.",
                    "scope_id": "opening",
                    "audience": "continuity",
                    "importance": "high",
                },
                {
                    "kind": "inventory_add",
                    "character_id": "tev-pc-1",
                    "item_id": "ring-key",
                    "name": "Ring key",
                    "descriptor": "Opens the boiler stair.",
                    "qty": 2,
                    "effect_tags": ["key", "boiler"],
                },
                {
                    "kind": "inventory_remove",
                    "character_id": "tev-pc-1",
                    "item_id": "spent-flare",
                    "qty": 1,
                },
            ]
            result = mcp_server.glass_state_update(
                updates=updates,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["args"], [])
        service.assert_called_once_with(updates=updates)

    def test_mcp_state_update_rejects_string_updates_with_instruction(self) -> None:
        result = mcp_server.glass_state_update(
            updates=[
                "audience=continuity; scope=opening; subject=gate; predicate=status; text=closed"
            ],
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], 77)
        self.assertIn("never strings", result["output"])
        self.assertIn('"kind": "fact"', result["output"])
        self.assertIn("Do not work around this failed tool call", result["instructions"][0])

    def test_mcp_check_calls_service_without_command_executor(self) -> None:
        with patch(
            "cli.mcp_server.check_service",
            return_value={"ready_for_done": True},
        ) as service:
            result = mcp_server.glass_check(no_mark=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["args"], [])
        service.assert_called_once_with(
            command_path="glass_check",
            emit_output=False,
            no_mark=True,
        )

    def test_mcp_fact_pack_and_lore_use_services(self) -> None:
        with (
            patch(
                "cli.mcp_server.fact_pack_service",
                return_value={"facts": []},
            ) as fact_pack,
            patch(
                "cli.mcp_server.lore_search_service",
                return_value={"entries": []},
            ) as lore_search,
        ):
            fact_result = mcp_server.glass_fact_pack(
                output_format="yaml",
                scene_id="opening",
                actor="tev",
                audience="profile",
                limit=12,
            )
            lore_result = mcp_server.glass_lore_search(query="salt", limit=3)

        self.assertTrue(fact_result["ok"])
        self.assertEqual(fact_result["args"], [])
        self.assertTrue(lore_result["ok"])
        self.assertEqual(lore_result["args"], [])
        fact_pack.assert_called_once_with(
            scene_id="opening",
            actor="tev",
            audience="profile",
            limit=12,
        )
        lore_search.assert_called_once_with(query="salt", limit=3)

    def test_mcp_messages_use_services(self) -> None:
        with (
            patch(
                "cli.mcp_server.send_message_service",
                return_value={"message": {"id": "m1"}},
            ) as send_service,
            patch(
                "cli.mcp_server.read_messages_service",
                return_value={"messages": [], "count": 0},
            ) as read_service,
        ):
            send_result = mcp_server.glass_message_send(
                message_type="proposal",
                recipient="dm",
                body="The gate should fail.",
            )
            read_result = mcp_server.glass_message_read(
                since_checkpoint=True,
                sender="tev",
                message_type="proposal",
                no_mark=True,
            )

        self.assertTrue(send_result["ok"])
        self.assertEqual(send_result["args"], [])
        self.assertTrue(read_result["ok"])
        self.assertEqual(read_result["args"], [])
        send_service.assert_called_once_with(
            command_path="glass_message_send",
            emit_output=False,
            message_type="proposal",
            recipient="dm",
            body="The gate should fail.",
        )
        read_service.assert_called_once_with(
            command_path="glass_message_read",
            emit_output=False,
            since_checkpoint=True,
            sender="tev",
            message_type="proposal",
            no_mark=True,
        )

    def test_mcp_character_new_calls_service_without_http_api(self) -> None:
        with patch(
            "cli.mcp_server.create_character_service",
            return_value={"character": {"character_id": "tev-pc-1"}},
        ) as service:
            result = mcp_server.glass_character_new(
                character_id="tev-pc-1",
                player_id="tev",
                name="Tev Arrol",
                species="human",
                culture="Sithari",
                archetype="Signal-knife usher",
                organization_role="door guard",
                bio="Keeps the bad stair clear when everyone else has to run.",
                primary_drive="care/protection",
                positive_trait="Keeps a spare joke ready for whoever looks cold.",
                table_presence="Invites others to mark routes on his battered slate.",
                non_work_want="Wants a dinner where nobody has to watch the door.",
                opening_social_action="Hands Sumi a dry cord and asks what route she trusts.",
                pull_utilization={
                    "source": "municipal ferry dispatch boards",
                    "thesis": "Tev treats danger like routing strangers through bad weather.",
                },
                starting_items=[
                    {
                        "item_id": "route-slate",
                        "name": "Route slate",
                        "descriptor": "battered route slate",
                        "qty": 1,
                        "effect_tags": ["route", "coordination"],
                    }
                ],
                facts=[
                    {
                        "subject_id": "tev-pc-1",
                        "predicate": "identity",
                        "text": "Tev is a door guard who routes people through danger.",
                        "audience": "continuity",
                        "importance": "high",
                    },
                    {
                        "subject_id": "tev-pc-1",
                        "predicate": "social-texture",
                        "text": "Tev offers route marks when people need steadiness.",
                        "audience": "profile",
                        "importance": "medium",
                    },
                ],
                goals=["Get the crew through.", "Pay the stair debt."],
                life_prompts=[
                    {
                        "prompt": "what they do when praised",
                        "answer": "They redirect credit to whoever held the line.",
                    },
                    {
                        "prompt": "what they collect",
                        "answer": "They keep bent route tags sorted by crossing.",
                    },
                ],
                skills={
                    "artisan": {"name": "route reading"},
                    "apprentices": [{"name": "door work"}, {"name": "dock talk"}],
                },
                attributes=[{"name": "focus", "tier": "advanced"}],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["args"], [])
        service.assert_called_once()
        kwargs = service.call_args.kwargs
        self.assertEqual(kwargs["command_path"], "glass_character_new")
        self.assertFalse(kwargs["emit_output"])
        self.assertEqual(kwargs["character_id"], "tev-pc-1")
        self.assertEqual(kwargs["goals"], ("Get the crew through.", "Pay the stair debt."))
        self.assertEqual(
            kwargs["life_prompts"],
            (
                "what they do when praised=They redirect credit to whoever held the line.",
                "what they collect=They keep bent route tags sorted by crossing.",
            ),
        )
        self.assertEqual(kwargs["attribute_values"], ("focus=advanced",))
        self.assertEqual(
            kwargs["skill_values"],
            ("route reading=artisan", "door work=apprentice", "dock talk=apprentice"),
        )
        self.assertEqual(
            kwargs["starting_items"],
            (
                {
                    "id": "route-slate",
                    "name": "Route slate",
                    "descriptor": "battered route slate",
                    "qty": 1,
                    "effect_tags": ["route", "coordination"],
                },
            ),
        )
        self.assertEqual([spec.audience for spec in kwargs["fact_specs"]], ["continuity", "profile"])
        self.assertEqual([spec.salience for spec in kwargs["fact_specs"]], ["high", "medium"])
        self.assertEqual(
            kwargs["pull_utilization"],
            "Source: municipal ferry dispatch boards; Thesis: Tev treats danger like routing strangers through bad weather.",
        )

    def test_mcp_character_read_and_signature_tools_use_services(self) -> None:
        with (
            patch(
                "cli.mcp_server.get_character_service",
                return_value={"character": {"character_id": "tev-pc-1"}},
            ) as get_service,
            patch(
                "cli.mcp_server.add_signature_move_service",
                return_value={"move": {"name": "Clean Cut"}},
            ) as add_service,
        ):
            get_result = mcp_server.glass_character_get("tev-pc-1")
            add_result = mcp_server.glass_character_signature_add(
                character_id="tev-pc-1",
                name="Clean Cut",
                descriptor="the clean cut",
                body="Free text move body.",
                look="A still wrist.",
                use="When a line must close.",
                tell="Leaves salt glass.",
            )

        self.assertTrue(get_result["ok"])
        self.assertEqual(get_result["args"], [])
        self.assertTrue(add_result["ok"])
        self.assertEqual(add_result["args"], [])
        get_service.assert_called_once_with(
            command_path="glass_character_get",
            character_id="tev-pc-1",
            agent_projection=True,
        )
        add_service.assert_called_once_with(
            command_path="glass_character_signature_add",
            emit_output=False,
            character_id="tev-pc-1",
            name="Clean Cut",
            descriptor="the clean cut",
            body="Free text move body.",
            look="A still wrist.",
            usual_use="When a line must close.",
            tell="Leaves salt glass.",
        )

    def test_mcp_campaign_planning_tools_use_services(self) -> None:
        with (
            patch(
                "cli.mcp_server.create_arc_service",
                return_value={"arc_id": "first-arc"},
            ) as create_arc,
            patch(
                "cli.mcp_server.end_mode_service",
                return_value={"ended": {"mode": "campaign-planning"}},
            ) as end_mode,
        ):
            mcp_server.glass_arc_create(
                "first-arc",
                "flood-control pump stations",
                "Gate timing shapes the opening pressure.",
            )
            mcp_server.glass_mode_end()

        create_arc.assert_called_once_with(
            command_path="glass_arc_create",
            emit_output=False,
            arc_id="first-arc",
            pull_source="flood-control pump stations",
            pull_utilization="Gate timing shapes the opening pressure.",
        )
        end_mode.assert_called_once_with(
            command_path="glass_mode_end",
            emit_output=False,
        )

    def test_mcp_done_calls_service_without_http_api(self) -> None:
        with patch(
            "cli.mcp_server.done_service",
            return_value={"valid": True},
        ) as service:
            result = mcp_server.glass_done(
                summary="Tev holds the gate.",
                state=["gate held", "worker freed"],
                rolls="focus 12 vs 10",
                scene_status="active",
                next_speaker="dm",
                turn_type="act",
                open_questions=["who takes the hose?"],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["args"], [])
        kwargs = service.call_args.kwargs
        self.assertEqual(kwargs["command_path"], "glass_done")
        self.assertFalse(kwargs["emit_output"])
        self.assertEqual(kwargs["summary"], "Tev holds the gate.")
        self.assertEqual(kwargs["state_changes"], ("gate held", "worker freed"))
        self.assertEqual(kwargs["rolls"], "focus 12 vs 10")
        self.assertEqual(kwargs["turn_type"], "act")
        self.assertEqual(kwargs["next_speaker"], "dm")
        self.assertEqual(kwargs["scene_status"], "active")
        self.assertEqual(kwargs["open_questions"], ("who takes the hose?",))
        self.assertEqual(kwargs["position"], "")
        self.assertEqual(kwargs["pressure"], "")
        self.assertNotIn("facts", kwargs)

    def test_mcp_turn_append_calls_service_without_command_executor(self) -> None:
        with patch(
            "cli.mcp_server.append_turn_service",
            return_value={"turn": {"turn_id": 7}},
        ) as service:
            result = mcp_server.glass_turn_append(body="Tev holds the gate.")

        self.assertTrue(result["ok"])
        self.assertEqual(result["args"], [])
        service.assert_called_once_with(
            command_path="glass_turn_append",
            emit_output=False,
            body="Tev holds the gate.",
            source="mcp",
        )

    def test_mcp_scene_transition_uses_service(self) -> None:
        with patch(
            "cli.mcp_server.scene_transition_service",
            return_value={"kind": "new"},
        ) as service:
            result = mcp_server.glass_scene_transition(
                next_scene_id="boiler-room",
                kind="new",
                scene_type="action",
                arc_id="caulden-rack",
                new_mode="action",
                summary="The dock raid breaks.",
                outcomes=["Tev holds the line."],
                xp="tev=3,sumi=3,renno=3,kit=3",
                carry_clocks=["alarm=still rising"],
                retire_clocks=["dock-door=resolved"],
                force=True,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["args"], [])
        service.assert_called_once_with(
            command_path="glass_scene_transition",
            emit_output=False,
            next_scene_id="boiler-room",
            kind="new",
            close_parent=False,
            scene_type="action",
            arc_id_override="caulden-rack",
            new_mode="action",
            summary="The dock raid breaks.",
            outcome_values=("Tev holds the line.",),
            beats=None,
            xp_spec="tev=3,sumi=3,renno=3,kit=3",
            carry_clock_specs=("alarm=still rising",),
            retire_clock_specs=("dock-door=resolved",),
            parent_summary=None,
            parent_outcome_values=(),
            parent_beats=None,
            parent_carry_clock_specs=(),
            parent_retire_clock_specs=(),
            force=True,
        )

    def test_mcp_roll_calls_service(self) -> None:
        with patch(
            "cli.mcp_server.roll_service",
            return_value={
                "outcome": "advance",
                "instructions": ["Carry this exact outcome forward."],
            },
        ) as roll_service:
            roll_result = mcp_server.glass_roll(
                character_id="tev-pc-1",
                skill="duel cleanly",
                attribute="finesse",
                risk="risky",
                target_id="patrol-leader",
                save_skill=True,
            )

        self.assertTrue(roll_result["ok"])
        self.assertEqual(roll_result["args"], [])
        self.assertEqual(roll_result["instructions"], ["Carry this exact outcome forward."])
        self.assertIn("instructions:", roll_result["output"])
        roll_service.assert_called_once_with(
            command_path="glass_roll",
            emit_output=False,
            skill="duel cleanly",
            attribute="finesse",
            risk="risky",
            character_id="tev-pc-1",
            target_id="patrol-leader",
            save_skill=True,
        )

    def test_mcp_scene_pressure_calls_service(self) -> None:
        with patch(
            "cli.mcp_server.pressure_scene_service",
            return_value={"reduction": 2},
        ) as pressure_service:
            result = mcp_server.glass_scene_pressure(
                target_id="reach-lower-ledge",
                character_id="tev-pc-1",
                skill="ladder work",
                attribute="finesse",
                risk="standard",
                impact="d6",
                bonus=1,
                save_skill=True,
                because="good rope angle",
                note="Tev gets below the first safe bracket.",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["args"], [])
        pressure_service.assert_called_once_with(
            command_path="glass_scene_pressure",
            emit_output=False,
            target_id="reach-lower-ledge",
            skill="ladder work",
            attribute="finesse",
            risk="standard",
            character_id="tev-pc-1",
            impact_die="d6",
            bonus=1,
            save_skill=True,
            because="good rope angle",
            note="Tev gets below the first safe bracket.",
        )

    def test_mcp_command_does_not_proxy_through_glass_cli(self) -> None:
        env = {"GLASS_API_URL": "http://127.0.0.1:26001", "GLASS_API_GRANT": "grant"}

        self.assertFalse(should_proxy(["mcp", "serve"], env))
        self.assertTrue(should_proxy(["check"], env))

    def test_mcp_stdio_server_lists_typed_tools(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo / "src")

        async def scenario() -> None:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "cli.mcp_server"],
                cwd=repo,
                env=env,
            )
            with open(os.devnull, "w", encoding="utf-8") as errlog:
                async with stdio_client(params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        tool_names = {tool.name for tool in tools.tools}
                        tools_by_name = {tool.name: tool for tool in tools.tools}
                        bad_state_update = await session.call_tool(
                            "glass_state_update",
                            {"updates": ["audience=continuity; subject=gate"]},
                        )

            self.assertIn("glass_state_update", tool_names)
            self.assertIn("glass_turn_append", tool_names)
            self.assertIn("glass_scene_transition", tool_names)
            self.assertIn("glass_roll", tool_names)
            self.assertIn("glass_help", tool_names)
            self.assertNotIn("glass_fact_set", tool_names)
            self.assertNotIn("glass_character_inventory_add", tool_names)
            self.assertNotIn("glass_character_inventory_remove", tool_names)
            self.assertNotIn("glass_tool_list", tool_names)
            self.assertNotIn("glass_command", tool_names)
            for name, tool in tools_by_name.items():
                if name.startswith("glass_"):
                    self.assertTrue(
                        (tool.description or "").strip(),
                        f"{name} is missing a tools/list description",
                    )
                    self.assertEqual(
                        tool.inputSchema.get("type"),
                        "object",
                        f"{name} is missing a structured tools/list input schema",
                    )
            self.assertIn(
                "parameter help",
                tools_by_name["glass_help"].description,
            )
            self.assertTrue(bad_state_update.isError)
            self.assertIn("typed objects, not strings", bad_state_update.content[0].text)
            state_update_schema = tools_by_name["glass_state_update"].inputSchema
            self.assertIn("updates", state_update_schema["required"])
            updates_schema = state_update_schema["properties"]["updates"]
            self.assertEqual(updates_schema["minItems"], 1)
            state_defs = state_update_schema["$defs"]
            self.assertEqual(
                state_defs["StateFactUpdate"]["properties"]["audience"]["enum"],
                ["continuity", "profile", "meta"],
            )
            self.assertIn("importance", state_defs["StateFactUpdate"]["required"])
            self.assertIn(
                '"importance"',
                json.dumps(state_defs["StateFactUpdate"]),
            )
            for value in ["high", "medium", "low", "minor"]:
                self.assertIn(value, json.dumps(state_defs["StateFactUpdate"]))
            self.assertEqual(
                state_defs["StateInventoryAdd"]["properties"]["kind"]["const"],
                "inventory_add",
            )
            self.assertEqual(
                state_defs["StateInventoryRemove"]["properties"]["kind"]["const"],
                "inventory_remove",
            )
            self.assertFalse(state_defs["StateFactUpdate"]["additionalProperties"])
            self.assertFalse(state_defs["StateInventoryAdd"]["additionalProperties"])
            self.assertFalse(state_defs["StateInventoryRemove"]["additionalProperties"])
            character_new_schema = tools_by_name["glass_character_new"].inputSchema
            self.assertLessEqual(
                {
                    "goals",
                    "life_prompts",
                    "skills",
                    "pull_utilization",
                    "starting_items",
                    "facts",
                },
                set(character_new_schema["required"]),
            )
            self.assertEqual(
                character_new_schema["properties"]["goals"]["minItems"],
                2,
            )
            self.assertEqual(
                character_new_schema["properties"]["goals"]["maxItems"],
                3,
            )
            self.assertEqual(
                character_new_schema["properties"]["life_prompts"]["minItems"],
                2,
            )
            self.assertEqual(
                character_new_schema["properties"]["life_prompts"]["maxItems"],
                3,
            )
            schema_text = json.dumps(character_new_schema)
            self.assertNotIn("name=tier", schema_text)
            self.assertNotIn("prompt=concrete behavior", schema_text)
            self.assertNotIn("Source:", schema_text)
            self.assertNotIn("--", schema_text)
            defs = character_new_schema["$defs"]
            fact_update_schema_text = json.dumps(defs["FactUpdate"])
            self.assertIn("importance", defs["FactUpdate"]["required"])
            for value in ["high", "medium", "low", "minor"]:
                self.assertIn(value, fact_update_schema_text)
            self.assertEqual(
                defs["CharacterAttribute"]["properties"]["name"]["enum"],
                [
                    "vitality",
                    "finesse",
                    "focus",
                    "resolve",
                    "attunement",
                    "ingenuity",
                    "presence",
                ],
            )
            self.assertEqual(
                defs["CharacterAttribute"]["properties"]["tier"]["enum"],
                [
                    "rudimentary",
                    "standard",
                    "advanced",
                    "superior",
                    "transcendent",
                ],
            )
            self.assertEqual(
                defs["CharacterStartingSkills"]["properties"]["apprentices"]["minItems"],
                2,
            )
            self.assertEqual(
                defs["CharacterStartingSkills"]["properties"]["apprentices"]["maxItems"],
                2,
            )
            self.assertLessEqual(
                {
                    "source",
                    "thesis",
                },
                set(defs["CharacterPullUtilization"]["required"]),
            )
            self.assertNotIn("CharacterPullSurfaces", defs)
            self.assertEqual(
                defs["CharacterStartingItem"]["properties"]["qty"]["minimum"],
                1,
            )
            self.assertEqual(
                tools_by_name["glass_scene_pressure"].inputSchema["properties"]["risk"]["enum"],
                ["controlled", "standard", "risky", "desperate"],
            )
            self.assertEqual(
                tools_by_name["glass_scene_pressure"].inputSchema["properties"]["impact"]["enum"],
                ["d6", "d8", "d10"],
            )
            self.assertIn("glass_scene_tracker_set", tools_by_name)
            self.assertIn("glass_scene_tracker_tick", tools_by_name)
            self.assertIn("glass_scene_tracker_list", tools_by_name)
            self.assertEqual(
                tools_by_name["glass_fact_pack"].inputSchema["properties"]["audience"]["enum"],
                ["continuity", "profile", "meta", "all"],
            )
            self.assertIn(
                "audience",
                tools_by_name["glass_fact_pack"].inputSchema["required"],
            )
            self.assertEqual(
                tools_by_name["glass_done"].inputSchema["properties"]["turn_type"]["enum"],
                ["act", "answer", "support", "pass", ""],
            )
            done_schema = tools_by_name["glass_done"].inputSchema
            self.assertIn("scene_status", done_schema["required"])
            self.assertEqual(
                done_schema["properties"]["scene_status"]["enum"],
                ["active", "closing", "ending", "ended", "blocked"],
            )
            self.assertNotIn("facts", done_schema["properties"])
            self.assertNotIn("FactUpdate", done_schema.get("$defs", {}))
            self.assertNotIn("subject.predicate", json.dumps(done_schema))

        anyio.run(scenario)

    def test_mcp_stdio_tool_executes_without_http_api(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates = root / "templates"
            campaigns = root / "campaigns"
            (campaigns / "c1").mkdir(parents=True)
            templates.mkdir()
            config = root / "glass.toml"
            config.write_text(
                f'[paths]\ntemplates = "{templates}"\ncampaigns = "{campaigns}"\n',
                encoding="utf-8",
            )
            grant = mint_grant(
                campaigns,
                campaign_id="c1",
                role="player",
                actor="tev",
                glass_role="player:tev",
                turn_id="c1-t0001",
                ttl_seconds=60,
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(repo / "src")
            env["GLASS_CONFIG"] = str(config)
            env["GLASS_API_URL"] = "http://127.0.0.1:9"
            env["GLASS_API_GRANT"] = grant

            async def scenario() -> None:
                params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "cli.mcp_server"],
                    cwd=repo,
                    env=env,
                )
                with open(os.devnull, "w", encoding="utf-8") as errlog:
                    async with stdio_client(params, errlog=errlog) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool(
                                "glass_help",
                                {"command": "glass_check"},
                            )

                self.assertFalse(getattr(result, "isError", False))

            anyio.run(scenario)


if __name__ == "__main__":
    unittest.main()
