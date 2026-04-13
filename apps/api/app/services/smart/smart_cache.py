"""
Smart Cache - Caching & CDN Optimization (Enhancement 8.2)

Intelligent caching for repeated generation requests. Saves compute and reduces latency.
Uses Redis (AWS ElastiCache or REDIS_URL); no Modal. AWS-compatible.

Strategy:
  Level 1: Exact prompt match (Redis)
  Level 2: Semantic similarity > 0.95 (SentenceTransformer + Redis)
Storage: Redis (metadata + exact payload). TTL: 7 days (configurable).
Invalidation: On model update (call invalidate_cache()).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

CACHE_TTL = 604800  # 7 days
CACHE_TTL_FAST = 3600  # 1 hour for FAST/STANDARD previews


def _cache_ttl_for_quality(quality_tier: Optional[str]) -> int:
    """Shorter TTL for fast previews; 7 days for full quality."""
    t = (quality_tier or "").upper()
    if t in ("FAST", "STANDARD"):
        return CACHE_TTL_FAST
    return CACHE_TTL


def _redis_client():  # type: ignore[no-untyped-def]
    """Build Redis client from REDIS_URL or REDIS_HOST/REDIS_PASSWORD (AWS ElastiCache)."""
    try:
        import redis  # type: ignore[reportMissingImports]
    except ImportError:
        return None
    url = os.environ.get("REDIS_URL")
    if url:
        return redis.from_url(url, decode_responses=False)
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD") or None
    db = int(os.environ.get("REDIS_DB", "0"))
    return redis.Redis(
        host=host, port=port, password=password, db=db, decode_responses=False
    )


class SmartCache:
    """
    Intelligent caching for generation results.
    Level 1: Exact (prompt, mode, identity_id) → instant hit.
    Level 2: Semantic similarity > 0.95 for same identity_id → similar hit.
    Runs locally or on AWS; no Modal. Direct method calls.
    """

    def __init__(self) -> None:
        self._np: Any = None
        self._redis: Any = None
        self._encoder: Any = None
        self._encoder_ok = False
        self._redis_ok = False

        try:
            import numpy as np  # type: ignore[reportMissingImports]

            self._np = np
        except ImportError:
            pass

        try:
            self._redis = _redis_client()
            if self._redis is not None:
                self._redis.ping()
                self._redis_ok = True
        except Exception as e:
            print(f"[SmartCache] Redis unavailable: {e}. Cache disabled.")

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            self._encoder_ok = True
        except Exception as e:
            print(
                f"[SmartCache] SentenceTransformer unavailable: {e}. Semantic cache disabled."
            )

    def _compute_key(
        self,
        prompt: str,
        mode: str,
        identity_id: Optional[str],
        quality_tier: Optional[str] = None,
        style: Optional[str] = None,
        creative: Optional[float] = None,
    ) -> str:
        tier = (quality_tier or "BALANCED").upper()
        key_str = f"{prompt}:{mode}:{identity_id or ''}:tier={tier}"
        if style:
            key_str += f":style={style}"
        if creative is not None:
            key_str += f":creative={creative}"
        return f"gen:{hashlib.md5(key_str.encode()).hexdigest()}"

    def _ensure_np(self) -> Any:
        if self._np is None:
            try:
                import numpy as np  # type: ignore[reportMissingImports]

                self._np = np
            except ImportError:
                return None
        return self._np

    def check_cache(
        self,
        prompt: str,
        mode: str,
        identity_id: Optional[str] = None,
        quality_tier: Optional[str] = None,
        style: Optional[str] = None,
        creative: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if request can be served from cache.
        quality_tier used for key + semantic list (fast vs full separation).
        """
        if not self._redis_ok or self._redis is None:
            return None

        cache_key = self._compute_key(
            prompt, mode, identity_id, quality_tier, style, creative
        )
        try:
            raw = self._redis.get(cache_key)
        except Exception:
            return None

        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
                print("✨ Cache hit (exact)")
                return {
                    "type": "exact",
                    "images": data["images"],
                    "parsed_prompt": data.get("parsed_prompt"),
                    "execution_plan": data.get("execution_plan"),
                }
            except Exception:
                return None

        if identity_id and self._encoder_ok and self._encoder is not None:
            similar = self._find_similar(
                prompt, mode, identity_id, quality_tier=quality_tier, threshold=0.95
            )
            if similar:
                print("✨ Cache hit (semantic)")
                return {
                    "type": "semantic",
                    "images": similar["images"],
                    "original_prompt": similar["prompt"],
                    "similarity": float(similar["similarity"]),
                }

        print("❌ Cache miss")
        return None

    def _find_similar(
        self,
        prompt: str,
        mode: str,
        identity_id: str,
        quality_tier: Optional[str] = None,
        threshold: float = 0.95,
    ) -> Optional[Dict[str, Any]]:
        np = self._ensure_np()
        if np is None or self._redis is None or not self._encoder_ok:
            return None

        try:
            query_emb = self._encoder.encode([prompt], convert_to_numpy=True)[0]
        except Exception:
            return None

        tier = (quality_tier or "BALANCED").upper()
        candidates_key = f"semantic:{identity_id}:{mode}:tier={tier}"
        try:
            candidates = self._redis.lrange(candidates_key, 0, 99)
        except Exception:
            return None

        best: Optional[Dict[str, Any]] = None
        best_sim = threshold

        for raw in candidates or []:
            try:
                entry = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            emb = entry.get("embedding")
            if not emb:
                continue
            cand_emb = np.array(emb, dtype=np.float32)
            norm_q = np.linalg.norm(query_emb)
            norm_c = np.linalg.norm(cand_emb)
            if norm_q < 1e-9 or norm_c < 1e-9:
                continue
            sim = float(np.dot(query_emb, cand_emb) / (norm_q * norm_c))
            if sim > best_sim:
                best_sim = sim
                cache_key = entry.get("cache_key")
                if cache_key:
                    raw_payload = self._redis.get(cache_key)
                    if raw_payload:
                        try:
                            payload = json.loads(raw_payload.decode("utf-8"))
                            best = {
                                "prompt": entry.get("prompt", ""),
                                "images": payload.get("images", []),
                                "similarity": sim,
                            }
                        except Exception:
                            pass
                else:
                    best = {
                        "prompt": entry.get("prompt", ""),
                        "images": entry.get("images", []),
                        "similarity": sim,
                    }
        return best

    def _index_semantic(
        self,
        prompt: str,
        mode: str,
        identity_id: str,
        embedding: List[float],
        cache_key: str,
        quality_tier: Optional[str] = None,
    ) -> None:
        if self._redis is None:
            return
        tier = (quality_tier or "BALANCED").upper()
        key = f"semantic:{identity_id}:{mode}:tier={tier}"
        entry = json.dumps(
            {
                "prompt": prompt,
                "embedding": embedding,
                "cache_key": cache_key,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        try:
            self._redis.lpush(key, entry)
            self._redis.ltrim(key, 0, 99)
        except Exception:
            pass

    def store_result(
        self,
        prompt: str,
        mode: str,
        identity_id: Optional[str],
        images: List[Dict[str, Any]],
        parsed_prompt: Optional[Dict[str, Any]] = None,
        execution_plan: Optional[Dict[str, Any]] = None,
        quality_tier: Optional[str] = None,
        ttl: Optional[int] = None,
        style: Optional[str] = None,
        creative: Optional[float] = None,
    ) -> None:
        """Store generation result. ttl from quality_tier if not provided."""
        if not self._redis_ok or self._redis is None:
            return

        if ttl is None:
            ttl = _cache_ttl_for_quality(quality_tier)
        cache_key = self._compute_key(
            prompt, mode, identity_id, quality_tier, style, creative
        )
        payload = {
            "images": images,
            "parsed_prompt": parsed_prompt,
            "execution_plan": execution_plan,
        }
        try:
            self._redis.setex(cache_key, ttl, json.dumps(payload))
        except Exception as e:
            print(f"[SmartCache] store exact fail: {e}")
            return

        if identity_id and self._encoder_ok and self._encoder is not None:
            try:
                emb = self._encoder.encode([prompt], convert_to_numpy=True)[0]
                self._index_semantic(
                    prompt, mode, identity_id, emb.tolist(), cache_key, quality_tier
                )
            except Exception as e:
                print(f"[SmartCache] index semantic fail: {e}")

    def invalidate_cache(self) -> int:
        """Invalidate all cache entries (e.g. on model update). Returns count of deleted keys."""
        if not self._redis_ok or self._redis is None:
            return 0
        count = 0
        try:
            for key in self._redis.scan_iter(match="gen:*"):
                self._redis.delete(key)
                count += 1
            for key in self._redis.scan_iter(match="semantic:*"):
                self._redis.delete(key)
                count += 1
        except Exception as e:
            print(f"[SmartCache] invalidate fail: {e}")
        return count


def main() -> None:
    """Smoke test: check then store a fake result. Requires Redis (REDIS_URL or REDIS_HOST)."""
    c = SmartCache()
    hit = c.check_cache("test prompt", "REALISM", None)
    print(
        "check_cache (miss expected):",
        "exact" if hit and hit.get("type") == "exact" else "miss",
    )
    c.store_result(
        prompt="test prompt",
        mode="REALISM",
        identity_id=None,
        images=[
            {"image_base64": "e0=", "seed": 1, "prompt": "test", "scores": {"total": 0}}
        ],
        parsed_prompt={"full_prompt": "test"},
        execution_plan={"engines": []},
    )
    hit2 = c.check_cache("test prompt", "REALISM", None)
    print(
        "check_cache after store (exact hit expected):",
        hit2.get("type") if hit2 else "miss",
    )
    print("Done.")


# Optional FastAPI app for cache stats/health; reserved for future use.
# Importable as smart_cache_app so caching.__init__ does not break.
smart_cache_app = None

if __name__ == "__main__":
    main()
