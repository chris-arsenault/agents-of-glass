import unittest

from cli import facts


class FactParsingTests(unittest.TestCase):
    def test_parse_dotted_fact(self) -> None:
        spec = facts.parse_fact_spec(
            "mox.status = Mox is pinned in the second pipe.",
            default_scope_id="old-iron",
            audience="continuity",
        )

        self.assertEqual(spec.subject_id, "mox")
        self.assertEqual(spec.predicate, "status")
        self.assertEqual(spec.object_id, None)
        self.assertEqual(spec.scope_id, "old-iron")
        self.assertEqual(spec.text, "Mox is pinned in the second pipe.")
        self.assertEqual(spec.salience, "medium")

    def test_parse_relationship_fact(self) -> None:
        spec = facts.parse_fact_spec(
            "mera.trusts -> mox = Mera trusts Mox after plain speech.",
            default_scope_id="party",
            audience="continuity",
        )

        self.assertEqual(spec.subject_id, "mera")
        self.assertEqual(spec.predicate, "trusts")
        self.assertEqual(spec.object_id, "mox")
        self.assertEqual(spec.scope_id, "party")

    def test_parse_fact_audience_splits_profile_and_meta_from_continuity(self) -> None:
        continuity = facts.parse_fact_spec(
            "scene.objective = The crew must reach the pipe mouth.",
            audience="continuity",
        )
        profile = facts.parse_fact_spec(
            "mara-vey.social-texture = Mara Vey overtrades for sour candies.",
            audience="profile",
        )
        meta = facts.parse_fact_spec(
            "organization.public-constraints = Records, witnesses, custody, "
            "and later proof are not the mission engine.",
            audience="meta",
        )

        self.assertEqual(continuity.audience, "continuity")
        self.assertEqual(profile.audience, "profile")
        self.assertEqual(meta.audience, "meta")

    def test_fact_scope_normalizes_by_mode(self) -> None:
        spec = facts.FactSpec(
            subject_id="mox",
            predicate="status",
            text="Mox is pinned.",
            audience="continuity",
        )

        scene_scoped = facts._scope_fact_specs([spec], mode="scene-play", scene_id="opening")
        non_scene_scoped = facts._scope_fact_specs(
            [spec],
            mode="character-creation",
            scene_id="character-creation",
        )

        self.assertEqual(scene_scoped[0].scope_id, "opening")
        self.assertEqual(non_scene_scoped[0].scope_id, "campaign")

    def test_fact_scope_preserves_explicit_scope(self) -> None:
        spec = facts.FactSpec(
            subject_id="mox",
            predicate="status",
            text="Mox is pinned.",
            audience="continuity",
            scope_id="party",
        )

        scoped = facts._scope_fact_specs([spec], mode="scene-play", scene_id="opening")

        self.assertEqual(scoped[0].scope_id, "party")

    def test_dm_fact_pack_visibility_includes_public_and_dm(self) -> None:
        class _Result:
            result_set = []

        class _Graph:
            def __init__(self) -> None:
                self.calls = []

            def query(self, cypher, params):
                self.calls.append((cypher, params))
                return _Result()

        graph = _Graph()
        facts._fact_pack_graph(
            graph,
            campaign_id="c1",
            scene_id=None,
            actor="dm",
            visibility="dm",
            audience="continuity",
            limit=80,
        )

        _, params = graph.calls[0]
        self.assertEqual(params["visibilities"], ["public", "dm"])

    def test_fact_pack_filters_audience_and_infers_legacy_rows(self) -> None:
        class _Result:
            result_set = [
                [
                    "campaign",
                    "organization",
                    "public-constraints",
                    None,
                    "Records, witnesses, custody, and later proof are not the mission engine.",
                    "t1",
                    "normal",
                    1,
                    "2026-01-01T00:00:00Z",
                    None,
                ],
                [
                    "campaign",
                    "mara-vey",
                    "social-texture",
                    None,
                    "Mara Vey overtrades for sour candies.",
                    "t2",
                    "normal",
                    1,
                    "2026-01-01T00:00:01Z",
                    None,
                ],
                [
                    "campaign",
                    "scene",
                    "objective",
                    None,
                    "The crew must reach the pipe mouth.",
                    "t3",
                    "normal",
                    1,
                    "2026-01-01T00:00:02Z",
                    "continuity",
                ],
                [
                    "campaign",
                    "loose-color",
                    "description",
                    None,
                    "A minor label that should not drive play.",
                    "t4",
                    "low",
                    1,
                    "2026-01-01T00:00:03Z",
                    "continuity",
                ],
            ]

        class _Graph:
            def query(self, cypher, params):
                return _Result()

        continuity = facts._fact_pack_graph(
            _Graph(),
            campaign_id="c1",
            scene_id=None,
            actor="dm",
            visibility="dm",
            audience="continuity",
            limit=80,
        )
        profile = facts._fact_pack_graph(
            _Graph(),
            campaign_id="c1",
            scene_id=None,
            actor="dm",
            visibility="dm",
            audience="profile",
            limit=80,
        )

        self.assertEqual(
            [(row["subject_id"], row["predicate"]) for row in continuity], [("scene", "objective")]
        )
        self.assertEqual(continuity[0]["importance"], "medium")
        self.assertEqual(
            [(row["subject_id"], row["predicate"]) for row in profile],
            [("mara-vey", "social-texture")],
        )

    def test_fact_pack_omits_low_and_minor_even_from_all_reads(self) -> None:
        class _Result:
            result_set = [
                [
                    "campaign",
                    "crumb",
                    "descriptor",
                    None,
                    "A low-value descriptive crumb.",
                    "t1",
                    "minor",
                    0,
                    "2026-01-01T00:00:00Z",
                    "continuity",
                ],
            ]

        class _Graph:
            def query(self, cypher, params):
                return _Result()

        rows = facts._fact_pack_graph(
            _Graph(),
            campaign_id="c1",
            scene_id=None,
            actor="dm",
            visibility="dm",
            audience="all",
            limit=80,
        )

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
