from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover - exercised only when deps are missing
    aioredis = None  # type: ignore[assignment]

from .config import settings

logger = logging.getLogger(__name__)

_CACHE_KEY_PREFIX = "swarm:cache:"
_EMBED_MODEL: Any = None
_MODEL_UNAVAILABLE = object()


def _get_embedding_model() -> Any:
    """Lazy-load the embedding model so app startup stays fast."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model '%s'", settings.EMBEDDING_MODEL_NAME)
            _EMBED_MODEL = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        except Exception as exc:  # pragma: no cover - depends on local model env
            logger.warning("Semantic cache disabled: embedding model unavailable (%s)", exc)
            _EMBED_MODEL = _MODEL_UNAVAILABLE
    return None if _EMBED_MODEL is _MODEL_UNAVAILABLE else _EMBED_MODEL


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCache:
    """
    Vector-similarity cache for advisory queries.

    Redis is used when REDIS_URL is reachable. If Redis is missing or offline, the
    cache silently falls back to process-local memory so analysis never crashes.
    """

    def __init__(self, threshold: float = settings.SEMANTIC_CACHE_THRESHOLD):
        self.threshold = threshold
        self._redis_client: Optional[Any] = None
        self._redis_available: Optional[bool] = None
        self._in_memory_cache: List[Dict[str, Any]] = []

    async def _get_redis(self) -> Optional[Any]:
        if aioredis is None:
            self._redis_available = False
            return None
        if self._redis_available is False:
            return None
        if self._redis_client is None:
            try:
                client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1.5,
                    socket_timeout=1.5,
                )
                await client.ping()
                self._redis_client = client
                self._redis_available = True
                logger.info("Connected to Redis semantic cache at %s", settings.REDIS_URL)
            except Exception as exc:
                logger.warning("Redis unavailable; using in-memory semantic cache (%s)", exc)
                self._redis_available = False
                self._redis_client = None
        return self._redis_client

    async def _embed(self, text: str) -> Optional[List[float]]:
        if not text.strip():
            return None

        model = await asyncio.to_thread(_get_embedding_model)
        if model is None:
            return None

        try:
            embedding = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            return [float(value) for value in embedding]
        except Exception as exc:  # pragma: no cover - depends on model runtime
            logger.warning("Embedding generation failed (%s)", exc)
            return None

    async def _redis_entries(self) -> List[Dict[str, Any]]:
        redis = await self._get_redis()
        if not redis:
            return []

        entries: List[Dict[str, Any]] = []
        try:
            async for key in redis.scan_iter(match=f"{_CACHE_KEY_PREFIX}*"):
                raw = await redis.get(key)
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed semantic cache entry: %s", key)
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
        except Exception as exc:
            logger.warning("Redis cache read failed; falling back to memory (%s)", exc)
            self._redis_available = False
            self._redis_client = None
        return entries

    async def lookup(self, query: str) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
        """
        Return the cached result and similarity score when the threshold is met.
        """
        query_embedding = await self._embed(query)
        if query_embedding is None:
            return None, None

        entries = [*await self._redis_entries(), *self._in_memory_cache]

        best_result: Optional[Dict[str, Any]] = None
        best_similarity = 0.0

        for entry in entries:
            similarity = _cosine_similarity(query_embedding, entry.get("embedding", []))
            if similarity > best_similarity:
                best_similarity = similarity
                best_result = entry.get("result")

        if best_result is not None and best_similarity >= self.threshold:
            logger.info(
                "Semantic cache hit (similarity=%.4f, threshold=%.4f)",
                best_similarity,
                self.threshold,
            )
            return best_result, best_similarity

        logger.info(
            "Semantic cache miss (best_similarity=%.4f, threshold=%.4f)",
            best_similarity,
            self.threshold,
        )
        return None, None

    async def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Return a semantically matching cached result, if one exists."""
        result, _ = await self.lookup(query)
        return result

    async def set(self, query: str, result: Dict[str, Any]) -> None:
        """Store the query embedding and final AnalysisResult payload."""
        query_embedding = await self._embed(query)
        if query_embedding is None:
            return

        entry = {
            "query": query,
            "embedding": query_embedding,
            "result": result,
        }

        self._in_memory_cache.append(entry)

        redis = await self._get_redis()
        if not redis:
            return

        try:
            digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
            await redis.set(f"{_CACHE_KEY_PREFIX}{digest}", json.dumps(entry), ex=86400 * 7)
        except Exception as exc:
            logger.warning("Redis cache write failed; kept in memory (%s)", exc)
            self._redis_available = False
            self._redis_client = None


semantic_cache = SemanticCache()
