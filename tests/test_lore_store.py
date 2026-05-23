import unittest

from cli import lore_store
from cli.lore_store import LoreEntrySpec


class _QueryResult:
    def __init__(self, rows=None):
        self.result_set = rows or []


class _FakeGraph:
    def __init__(self, rows=None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.rows = rows or []

    def query(self, cypher: str, params: dict | None = None) -> _QueryResult:
        self.calls.append((cypher, params or {}))
        return _QueryResult(self.rows)


class LoreStoreTests(unittest.TestCase):
    def test_upsert_lore_entry_graph_stores_prose_without_file_path(self) -> None:
        fake = _FakeGraph()

        result = lore_store._upsert_lore_entry_graph(
            fake,
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

        cypher, params = fake.calls[0]
        self.assertIn("MERGE (entry:LoreEntry {uid: $uid})", cypher)
        self.assertEqual(params["uid"], "lore:reference:voice-rail")
        self.assertEqual(params["props"]["body_text"], "A signal network with strict operational limits.")
        self.assertNotIn("file_path", params["props"])
        self.assertEqual(result["namespace"], "reference")

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

    def test_search_lore_graph_filters_to_reference_and_campaign_namespaces(self) -> None:
        fake = _FakeGraph(
            rows=[
                [
                    "voice-rail",
                    "Voice Rail",
                    "concept",
                    "reference",
                    "public",
                    "source.md",
                    "The Voice Rail is a signal network.",
                    "2026-01-01T00:00:00Z",
                ]
            ]
        )

        rows = lore_store._search_lore_graph(
            fake,
            campaign_id="c1",
            terms=["voice", "rail"],
            limit=5,
            include_dm=False,
        )

        cypher, params = fake.calls[0]
        self.assertIn("MATCH (entry:LoreEntry)", cypher)
        self.assertEqual(params["namespaces"], ["reference", "c1"])
        self.assertEqual(params["visibilities"], ["public"])
        self.assertEqual(rows[0]["id"], "voice-rail")
        self.assertEqual(rows[0]["excerpt"], "The Voice Rail is a signal network.")


if __name__ == "__main__":
    unittest.main()
