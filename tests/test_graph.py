import unittest

from cli import graph


class _QueryResult:
    result_set = []


class _FakeGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def query(self, cypher: str, params: dict | None = None) -> _QueryResult:
        self.calls.append((cypher, params or {}))
        return _QueryResult()


class GraphQueryTests(unittest.TestCase):
    def test_upsert_entity_uses_campaign_scoped_uid_and_clears_shell_status(self) -> None:
        fake = _FakeGraph()

        graph.upsert_entity(
            fake,
            entity_id="ringglass",
            campaign_id="c1",
            title="Ringglass",
            entity_type="concept",
            file_path="shared/lore/concepts/ringglass.md",
        )

        cypher, params = fake.calls[0]
        self.assertIn("MERGE (e:Entity {uid: $uid})", cypher)
        self.assertEqual(params["uid"], "c1:ringglass")
        self.assertEqual(params["id"], "ringglass")
        self.assertEqual(params["campaign_id"], "c1")
        self.assertIsNone(params["status"])

    def test_neighborhood_query_uses_campaign_scoped_uid(self) -> None:
        fake = _FakeGraph()

        result = graph.neighborhood(fake, "ringglass", campaign_id="c1")

        self.assertEqual(result, {"found": False, "entity_id": "ringglass"})
        cypher, params = fake.calls[0]
        self.assertIn("MATCH (e:Entity {uid: $uid})", cypher)
        self.assertIn("collect(DISTINCT {type: type(r_out)", cypher)
        self.assertEqual(params, {"uid": "c1:ringglass"})


if __name__ == "__main__":
    unittest.main()
