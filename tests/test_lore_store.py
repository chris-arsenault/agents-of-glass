import tempfile
import unittest
from pathlib import Path

from cli import db, lore_store
from cli.lore_store import LoreEntrySpec


class LoreStoreTests(unittest.TestCase):
    def test_upsert_lore_entry_stores_prose_without_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with db.connect(db.StorageConfig(Path(tmp) / "store.sqlite3")) as conn:
                result = lore_store._upsert_lore_entry_storage(
                    conn,
                    campaign_id="c1",
                    spec=LoreEntrySpec(
                        lore_id="voice-rail",
                        title="Voice Rail",
                        body="A signal network with strict operational limits.",
                        kind="concept",
                        namespace="reference",
                        source="world-bible/concepts/voice-rail.md",
                        tags=("signal", "rail"),
                    ),
                )
                rows = lore_store._list_lore_storage(
                    conn,
                    campaign_id="c1",
                    limit=5,
                    include_dm=False,
                )

        self.assertEqual(result["uid"], "lore:reference:voice-rail")
        self.assertEqual(result["namespace"], "reference")
        self.assertEqual(rows[0]["excerpt"], "A signal network with strict operational limits.")

    def test_reference_terms_come_from_facts_not_agent_query(self) -> None:
        pack = {
            "facts": [
                {
                    "subject_id": "voice-rail-pylon",
                    "object_id": "amber-compact",
                    "text": "The dormant Voice Rail pylon is visible near the dock.",
                }
            ]
        }

        terms = lore_store._terms_from_fact_pack(pack)

        self.assertIn("voice", terms)
        self.assertIn("rail", terms)
        self.assertIn("pylon", terms)
        self.assertIn("amber", terms)
        self.assertNotIn("scene", terms)

    def test_search_lore_filters_to_reference_and_campaign_namespaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with db.connect(db.StorageConfig(Path(tmp) / "store.sqlite3")) as conn:
                lore_store._upsert_lore_entry_storage(
                    conn,
                    campaign_id="c1",
                    spec=LoreEntrySpec(
                        lore_id="voice-rail",
                        title="Voice Rail",
                        body="The Voice Rail is a signal network.",
                        kind="concept",
                        namespace="reference",
                        source="source.md",
                    ),
                )
                lore_store._upsert_lore_entry_storage(
                    conn,
                    campaign_id="c2",
                    spec=LoreEntrySpec(
                        lore_id="other-campaign",
                        title="Other Voice Rail",
                        body="This must stay scoped to c2.",
                        namespace="c2",
                    ),
                )
                rows = lore_store._search_lore_storage(
                    conn,
                    campaign_id="c1",
                    terms=["voice", "rail"],
                    limit=5,
                    include_dm=False,
                )

        self.assertEqual(rows[0]["id"], "voice-rail")
        self.assertEqual(rows[0]["excerpt"], "The Voice Rail is a signal network.")
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
