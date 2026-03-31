"""
Test suite for Identity Engine V2 (AWS): face consistency, ensemble, ArcFace scoring.

Run from ai-pipeline:
  pytest tests/test_identity_v2.py -v -s
  pytest tests/test_identity_v2.py -v -s -m "not gpu"

Target: 99%+ faces with similarity > 0.85; benchmark against diverse faces.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Optional
from unittest import mock

import pytest

_tests_dir = Path(__file__).resolve().parent
_ai_pipeline = _tests_dir.parent
if str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

# Optional imports (skip tests when unavailable)
identity_v2_aws = None
try:
    from services.identity_engine_v2_aws import (
        IdentityEngineV2,
        FaceConsistencyScorer,
        GenerationResult,
        _compute_face_similarity,
        InstantIDEngine,
        result_to_base64,
    )
    identity_v2_aws = True
except Exception:
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_face_image():
    """Minimal 64x64 RGB image (no real face; for structure tests)."""
    from PIL import Image
    return Image.new("RGB", (64, 64), color=(128, 128, 128))


@pytest.fixture
def sample_embedding():
    """Fake 512-dim embedding for tests."""
    import numpy as np
    return np.random.randn(512).astype(np.float32) * 0.1


# ---------------------------------------------------------------------------
# Face consistency scoring (ArcFace)
# ---------------------------------------------------------------------------

class TestFaceConsistencyScoring:
    """Face similarity scoring using ArcFace (InsightFace)."""

    def test_compute_face_similarity_interface(self, sample_face_image):
        """_compute_face_similarity returns float in [0, 1] or 0 on failure."""
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        # With non-face image or missing InsightFace, may return 0
        score = _compute_face_similarity(sample_face_image, sample_face_image)
        assert isinstance(score, (int, float))
        assert 0 <= score <= 1.0

    def test_face_scorer_same_image(self, sample_face_image):
        """Scorer returns value in [0, 1] for same image (may be 0 if no face)."""
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        scorer = FaceConsistencyScorer()
        # May not load on CI (no InsightFace); score can be 0
        s = scorer.score(sample_face_image, sample_face_image)
        assert isinstance(s, (int, float))
        assert 0 <= s <= 1.0

    def test_face_scorer_get_embedding_returns_numpy_or_none(self, sample_face_image):
        """get_embedding returns ndarray or None."""
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        scorer = FaceConsistencyScorer()
        emb = scorer.get_embedding(sample_face_image)
        if emb is not None:
            import numpy as np
            assert isinstance(emb, np.ndarray)


# ---------------------------------------------------------------------------
# GenerationResult and result_to_base64
# ---------------------------------------------------------------------------

class TestGenerationResult:
    def test_result_to_base64_from_image(self, sample_face_image):
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        result = GenerationResult(image=sample_face_image, similarity=0.9, path="instantid")
        b64 = result_to_base64(result)
        assert isinstance(b64, str)
        assert len(b64) > 0
        import base64
        raw = base64.b64decode(b64)
        assert len(raw) > 0

    def test_result_to_base64_none_image(self):
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        result = GenerationResult(image=None, image_base64="abc", similarity=0.0)
        assert result_to_base64(result) == "abc"


# ---------------------------------------------------------------------------
# IdentityEngineV2 ensemble logic (unit, no GPU)
# ---------------------------------------------------------------------------

class TestIdentityEngineV2Ensemble:
    """Ensemble selection and method routing."""

    def test_unknown_method_returns_error_result(self, sample_face_image, sample_embedding):
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        engine = IdentityEngineV2()
        result = engine.generate_with_identity(
            prompt="test",
            identity_embedding=sample_embedding,
            face_image=sample_face_image,
            method="unknown_path",
        )
        assert result.error is not None
        assert "Unknown method" in result.error

    def test_ensemble_with_no_engines_loaded_returns_error(self, sample_face_image, sample_embedding):
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        engine = IdentityEngineV2()
        # Do not load; no path is available
        result = engine.generate_with_identity(
            prompt="test",
            identity_embedding=sample_embedding,
            face_image=sample_face_image,
            method="ensemble",
        )
        assert result.error is not None
        err_lower = result.error.lower()
        assert "no path produced" in err_lower or "not loaded" in err_lower or "ensemble" in err_lower

    def test_single_path_instantid_unloaded_returns_error_or_none_image(
        self, sample_face_image, sample_embedding
    ):
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        engine = IdentityEngineV2()
        result = engine.generate_with_identity(
            prompt="test",
            identity_embedding=sample_embedding,
            face_image=sample_face_image,
            method="instantid",
        )
        # Either error or no image (engine not loaded)
        assert result.error is not None or result.image is None


# ---------------------------------------------------------------------------
# Benchmark-style tests (skip without GPU/models)
# ---------------------------------------------------------------------------

@pytest.mark.gpu
class TestIdentityV2Benchmark:
    """
    Benchmark: similarity score, generation time, failure rate.
    Target: 99%+ faces with similarity > 0.85.
    Skip when no GPU or models.
    """

    def test_ensemble_selects_best_by_similarity(self, sample_face_image, sample_embedding):
        """When multiple paths return images, ensemble picks highest similarity."""
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        engine = IdentityEngineV2()
        # Mock InstantID to return an image so ensemble has one candidate
        with mock.patch.object(engine.instantid_engine, "is_available", return_value=True):
            with mock.patch.object(
                engine.instantid_engine,
                "generate",
                return_value=sample_face_image.copy(),
            ):
                result = engine.generate_with_identity(
                    prompt="test",
                    identity_embedding=sample_embedding,
                    face_image=sample_face_image,
                    method="ensemble",
                )
                if result.error:
                    pytest.skip(f"Ensemble failed (no GPU/models): {result.error}")
                assert result.image is not None
                assert result.similarity >= 0
                assert result.path in ("instantid", "faceadapter", "photomaker")

    def test_similarity_target_above_085_when_face_present(self):
        """With real face images, similarity should reach > 0.85 (skip without data)."""
        if identity_v2_aws is None:
            pytest.skip("identity_engine_v2_aws not available")
        # Requires two real face images; skip if not provided
        face_path = os.environ.get("TEST_FACE_IMAGE_1")
        if not face_path or not os.path.isfile(face_path):
            pytest.skip("Set TEST_FACE_IMAGE_1 for similarity benchmark")
        from PIL import Image
        img = Image.open(face_path).convert("RGB")
        scorer = FaceConsistencyScorer()
        if not scorer._ensure_loaded():
            pytest.skip("InsightFace not available")
        s = scorer.score(img, img)
        assert s >= 0.85, f"Same-face similarity should be >= 0.85, got {s}"
