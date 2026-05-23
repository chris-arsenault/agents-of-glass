import os
import unittest
from unittest.mock import patch

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
    def test_load_falkor_config_requires_explicit_host(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AOG_FALKOR_HOST": "",
                "AOG_FALKOR_PORT": "",
                "AOG_FALKOR_GRAPH": "",
                "AOG_FALKOR_PASSWORD": "",
                "REDIS_PASSWORD": "",
            },
            clear=False,
        ):
            for key in (
                "AOG_FALKOR_HOST",
                "AOG_FALKOR_PORT",
                "AOG_FALKOR_GRAPH",
                "AOG_FALKOR_PASSWORD",
                "REDIS_PASSWORD",
            ):
                os.environ.pop(key, None)
            with self.assertRaises(ValueError) as exc:
                graph.load_falkor_config({})

        self.assertIn("FalkorDB host is not configured", str(exc.exception))

    def test_load_falkor_config_uses_explicit_falkordb_section(self) -> None:
        config = graph.load_falkor_config(
            {
                "postgres": {"host": "postgres-only"},
                "falkordb": {
                    "host": "192.168.66.3",
                    "port": 16379,
                    "graph": "agents_of_glass",
                },
            }
        )

        self.assertEqual(config.host, "192.168.66.3")
        self.assertEqual(config.port, 16379)
        self.assertEqual(config.graph, "agents_of_glass")

    def test_load_falkor_config_never_falls_back_to_postgres_host(self) -> None:
        with self.assertRaises(ValueError):
            graph.load_falkor_config({"postgres": {"host": "192.168.66.3"}})

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
