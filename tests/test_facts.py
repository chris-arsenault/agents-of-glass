import tempfile
import unittest
from pathlib import Path

from cli import db, facts


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
        with tempfile.TemporaryDirectory() as tmp:
            with db.connect(db.StorageConfig(Path(tmp) / "store.sqlite3")) as conn:
                for subject, visibility in (
                    ("public-fact", "public"),
                    ("dm-fact", "dm"),
                    ("private-fact", "private"),
                ):
                    facts._set_fact_storage(
                        conn,
                        campaign_id="c1",
                        spec=facts.FactSpec(
                            subject_id=subject,
                            predicate="status",
                            text=f"{subject} text",
                            audience="continuity",
                            scope_id="campaign",
                            visibility=visibility,
                        ),
                        actor="dm",
                        turn_id="t1",
                        mode="scene-play",
                        scene_id=None,
                    )
                rows = facts._fact_pack_storage(
                    conn,
                    campaign_id="c1",
                    scene_id=None,
                    actor="dm",
                    visibility="dm",
                    audience="continuity",
                    limit=80,
                )

        self.assertEqual({row["subject_id"] for row in rows}, {"public-fact", "dm-fact"})

    def test_fact_pack_filters_audience(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with db.connect(db.StorageConfig(Path(tmp) / "store.sqlite3")) as conn:
                for subject, predicate, text, audience, salience in (
                    ("scene", "objective", "Reach the pipe mouth.", "continuity", "medium"),
                    ("mara-vey", "social-texture", "Trades for sour candies.", "profile", "medium"),
                    ("loose-color", "description", "A minor label.", "continuity", "low"),
                ):
                    facts._set_fact_storage(
                        conn,
                        campaign_id="c1",
                        spec=facts.FactSpec(
                            subject_id=subject,
                            predicate=predicate,
                            text=text,
                            audience=audience,
                            salience=salience,
                            scope_id="campaign",
                        ),
                        actor="dm",
                        turn_id="t1",
                        mode="scene-play",
                        scene_id=None,
                    )
                continuity = facts._fact_pack_storage(
                    conn,
                    campaign_id="c1",
                    scene_id=None,
                    actor="dm",
                    visibility="dm",
                    audience="continuity",
                    limit=80,
                )
                profile = facts._fact_pack_storage(
                    conn,
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
        with tempfile.TemporaryDirectory() as tmp:
            with db.connect(db.StorageConfig(Path(tmp) / "store.sqlite3")) as conn:
                facts._set_fact_storage(
                    conn,
                    campaign_id="c1",
                    spec=facts.FactSpec(
                        subject_id="crumb",
                        predicate="descriptor",
                        text="A low-value descriptive crumb.",
                        audience="continuity",
                        salience="minor",
                        scope_id="campaign",
                    ),
                    actor="dm",
                    turn_id="t1",
                    mode="scene-play",
                    scene_id=None,
                )
                rows = facts._fact_pack_storage(
                    conn,
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
