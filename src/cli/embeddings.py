"""Embedding provider client for search indexing and semantic recall."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
import json
import os
import urllib.error
import urllib.request

from .config import load_config
from .errors import GlassError


DEFAULT_EMBEDDING_URL = "http://192.168.66.3:5361/v1/embeddings"
DEFAULT_EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
DEFAULT_PROVIDER = "openai-compatible"
DEFAULT_BATCH_SIZE = 32
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DOCUMENT_PREFIX = "search_document: "
DEFAULT_QUERY_PREFIX = "search_query: "

EmbeddingKind = Literal["document", "query"]


@dataclass(frozen=True)
class EmbeddingConfig:
    url: str
    model: str
    provider: str
    timeout_seconds: float
    batch_size: int
    document_prefix: str
    query_prefix: str


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    model: str
    provider: str
    dimensions: int


def load_embedding_config(toml_data: dict[str, Any] | None = None) -> EmbeddingConfig:
    section = (toml_data or load_config()).get("embedding", {})
    if not isinstance(section, dict):
        section = {}
    return EmbeddingConfig(
        url=(
            os.environ.get("AOG_EMBEDDING_URL")
            or str(section.get("url") or DEFAULT_EMBEDDING_URL)
        ),
        model=(
            os.environ.get("AOG_EMBEDDING_MODEL")
            or str(section.get("model") or DEFAULT_EMBEDDING_MODEL)
        ),
        provider=str(section.get("provider") or DEFAULT_PROVIDER),
        timeout_seconds=float(
            os.environ.get("AOG_EMBEDDING_TIMEOUT_SECONDS")
            or section.get("timeout_seconds")
            or DEFAULT_TIMEOUT_SECONDS
        ),
        batch_size=max(
            1,
            int(
                os.environ.get("AOG_EMBEDDING_BATCH_SIZE")
                or section.get("batch_size")
                or DEFAULT_BATCH_SIZE
            ),
        ),
        document_prefix=str(section.get("document_prefix") or DEFAULT_DOCUMENT_PREFIX),
        query_prefix=str(section.get("query_prefix") or DEFAULT_QUERY_PREFIX),
    )


def embed_texts(
    texts: list[str],
    *,
    kind: EmbeddingKind,
    config: EmbeddingConfig | None = None,
) -> EmbeddingBatch:
    """Embed texts with the configured OpenAI-compatible provider."""
    if not texts:
        cfg = config or load_embedding_config()
        return EmbeddingBatch(vectors=[], model=cfg.model, provider=cfg.provider, dimensions=0)

    cfg = config or load_embedding_config()
    vectors: list[list[float]] = []
    returned_model = cfg.model
    for batch in _batches(texts, cfg.batch_size):
        payload = {
            "model": cfg.model,
            "input": [_prefix_text(text, kind=kind, config=cfg) for text in batch],
        }
        data = _post_embeddings(cfg, payload)
        batch_vectors, returned_model = _parse_embedding_response(data, expected=len(batch))
        vectors.extend(batch_vectors)

    dimensions = len(vectors[0]) if vectors else 0
    if any(len(vector) != dimensions for vector in vectors):
        raise GlassError("embedding provider returned vectors with inconsistent dimensions")
    return EmbeddingBatch(
        vectors=vectors,
        model=returned_model,
        provider=cfg.provider,
        dimensions=dimensions,
    )


def embed_text(
    text: str,
    *,
    kind: EmbeddingKind,
    config: EmbeddingConfig | None = None,
) -> EmbeddingBatch:
    return embed_texts([text], kind=kind, config=config)


def embedding_text(*, title: str | None, body: str) -> str:
    title = (title or "").strip()
    body = body.strip()
    if title and body:
        return f"{title}\n\n{body}"
    return title or body


def _prefix_text(text: str, *, kind: EmbeddingKind, config: EmbeddingConfig) -> str:
    prefix = config.query_prefix if kind == "query" else config.document_prefix
    stripped = text.strip()
    if stripped.startswith(prefix.strip()):
        return stripped
    return prefix + stripped


def _post_embeddings(config: EmbeddingConfig, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        config.url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GlassError(
            f"embedding provider failed at {config.url}: HTTP {exc.code}: {detail}"
        ) from exc
    except Exception as exc:
        raise GlassError(f"embedding provider failed at {config.url}: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GlassError(f"embedding provider returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GlassError("embedding provider returned a non-object response")
    return parsed


def _parse_embedding_response(
    data: dict[str, Any],
    *,
    expected: int,
) -> tuple[list[list[float]], str]:
    rows = data.get("data")
    if not isinstance(rows, list) or len(rows) != expected:
        raise GlassError(
            f"embedding provider returned {len(rows) if isinstance(rows, list) else 'no'} "
            f"vectors; expected {expected}"
        )
    ordered = sorted(rows, key=lambda row: int(row.get("index", 0)))
    vectors: list[list[float]] = []
    for row in ordered:
        vector = row.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise GlassError("embedding provider returned a row without an embedding")
        try:
            vectors.append([float(value) for value in vector])
        except (TypeError, ValueError) as exc:
            raise GlassError("embedding provider returned a non-numeric embedding") from exc
    return vectors, str(data.get("model") or "")


def _batches(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]
