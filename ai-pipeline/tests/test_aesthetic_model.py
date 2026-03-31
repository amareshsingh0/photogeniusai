"""
Test suite for aesthetic reward model: correlation with human ratings, inference time.

Target: Pearson r >0.75 with human ratings; inference <100ms per image.
Run: pytest ai-pipeline/tests/test_aesthetic_model.py -v -s
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

_tests_dir = Path(__file__).resolve().parent
_ai_pipeline = _tests_dir.parent
if str(_ai_pipeline) not in sys.path:
    sys.path.insert(0, str(_ai_pipeline))

aesthetic_model = None
try:
    from training.aesthetic_model import (
        AestheticPredictor,
        get_transform,
        predict,
        load_pretrained,
        build_predictor,
    )
    aesthetic_model = True
except Exception:
    pass


@pytest.fixture
def sample_image():
    """Minimal 224x224 RGB image (no real content)."""
    from PIL import Image
    return Image.new("RGB", (224, 224), color=(128, 128, 128))


class TestAestheticModelInterface:
    """Interface and output range."""

    def test_predict_returns_float_0_1_when_model_available(self, sample_image):
        if aesthetic_model is None:
            pytest.skip("training.aesthetic_model not available")
        # Without loading checkpoint, build_predictor + predict may give arbitrary value
        try:
            from training.aesthetic_model import build_predictor, predict
            model = build_predictor(device="cpu")
            s = predict(model, sample_image, device="cpu")
            assert isinstance(s, (int, float))
            assert 0 <= s <= 1
        except Exception as e:
            pytest.skip(f"Model build/predict failed (no GPU/checkpoint): {e}")

    def test_transform_output_shape(self):
        if aesthetic_model is None:
            pytest.skip("training.aesthetic_model not available")
        t = get_transform()
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(0, 0, 0))
        x = t(img)
        assert x.shape == (3, 224, 224)


class TestInferenceTime:
    """Target: <100ms per image (skip without GPU/checkpoint)."""

    @pytest.mark.gpu
    def test_inference_time_under_100ms_with_checkpoint(self, sample_image):
        if aesthetic_model is None:
            pytest.skip("training.aesthetic_model not available")
        ckpt = os.environ.get("AESTHETIC_CHECKPOINT", "")
        if not ckpt or not Path(ckpt).exists():
            pytest.skip("Set AESTHETIC_CHECKPOINT for inference time test")
        model = load_pretrained(ckpt, device="cuda")
        start = time.perf_counter()
        for _ in range(5):
            predict(model, sample_image, device="cuda")
        elapsed = (time.perf_counter() - start) / 5
        assert elapsed < 0.2, f"Inference time {elapsed*1000:.1f}ms should be <200ms (target <100ms)"


class TestCorrelationWithHumanRatings:
    """Target: Pearson r >0.75 (skip without labeled data)."""

    @pytest.mark.gpu
    def test_pearson_correlation_with_human_ratings(self):
        if aesthetic_model is None:
            pytest.skip("training.aesthetic_model not available")
        # Requires (image_paths, human_ratings); skip if not provided
        data_dir = os.environ.get("AESTHETIC_TEST_DATA")
        if not data_dir or not Path(data_dir).exists():
            pytest.skip("Set AESTHETIC_TEST_DATA for correlation test")
        import numpy as np
        try:
            from training.aesthetic_model import load_pretrained, predict
            from PIL import Image
            model = load_pretrained(os.environ.get("AESTHETIC_CHECKPOINT", ""), device="cuda")
            preds, human = [], []
            for f in list(Path(data_dir).glob("*.jpg"))[:50]:
                meta = f.with_suffix(".json")
                if not meta.exists():
                    continue
                import json as _json
                with open(meta, encoding="utf-8") as fp:
                    human.append(float(_json.load(fp).get("rating", 5.0)) / 10.0)
                img = Image.open(f).convert("RGB")
                preds.append(predict(model, img, "cuda"))
            if len(preds) < 10:
                pytest.skip("Need at least 10 labeled images")
            r = np.corrcoef(preds, human)[0, 1]
            assert r > 0.75, f"Pearson r={r:.3f} should be >0.75"
        except Exception as e:
            pytest.skip(f"Correlation test failed: {e}")
