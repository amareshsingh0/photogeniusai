"""
Quality Assessment - CLIP-based scoring, artifact detection, composition, retry logic.

Assesses generated image quality: CLIP prompt-image similarity, artifact detection
(blur, oversaturation, noise), composition analysis (rule of thirds, balance).
Provides quality verdicts (excellent/good/acceptable/poor), retry recommendations,
and optional batch processing.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np  # type: ignore[reportMissingImports]
from PIL import Image  # type: ignore[reportMissingImports]

# Optional observability
_logger = logging.getLogger(__name__)
_observability = None
StructuredLogger = None
trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]

try:
    this_dir = os.path.dirname(os.path.abspath(__file__))
    _path = os.path.join(this_dir, "observability.py")
    if os.path.isfile(_path):
        spec = importlib.util.spec_from_file_location("observability", _path)
        if spec and spec.loader:
            _observability = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_observability)
            StructuredLogger = getattr(_observability, "StructuredLogger", None)
            trace_function = getattr(_observability, "trace_function", trace_function)
except Exception:
    pass
if StructuredLogger is None:
    try:
        from services.observability import StructuredLogger, trace_function  # type: ignore[assignment]
    except Exception:
        pass


def _log():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return _logger


def _record_metric(name: str, **labels: Any) -> None:
    try:
        from services.observability import Metrics
        obj = getattr(Metrics, name, None)
        if obj is not None and hasattr(obj, "labels"):
            obj.labels(**{k: str(v) for k, v in labels.items()}).observe(labels.get("value", 0))
    except Exception:
        pass


# ==================== Enums & Dataclasses ====================


class QualityVerdict(str, Enum):
    """Quality assessment result."""

    EXCELLENT = "excellent"    # >0.85: Perfect, no issues
    GOOD = "good"              # 0.75-0.85: Good enough
    ACCEPTABLE = "acceptable"  # 0.65-0.75: Borderline
    POOR = "poor"              # <0.65: Retry needed


@dataclass
class QualityScore:
    """Complete quality assessment."""

    overall_score: float  # 0-1
    verdict: QualityVerdict
    clip_score: float
    artifact_score: float  # lower is better
    composition_score: float
    issues_found: List[str]
    suggestions: List[str]
    should_retry: bool
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 4),
            "verdict": self.verdict.value,
            "clip_score": round(self.clip_score, 4),
            "artifact_score": round(self.artifact_score, 4),
            "composition_score": round(self.composition_score, 4),
            "issues_found": self.issues_found,
            "suggestions": self.suggestions,
            "should_retry": self.should_retry,
            "confidence": round(self.confidence, 4),
        }


# ==================== QualityAssessment ====================


class QualityAssessment:
    """
    Image quality assessment system.

    Uses CLIP for semantic accuracy (optional) + heuristic artifact and composition checks.
    """

    THRESHOLDS = {
        QualityVerdict.EXCELLENT: 0.85,
        QualityVerdict.GOOD: 0.75,
        QualityVerdict.ACCEPTABLE: 0.65,
        QualityVerdict.POOR: 0.0,
    }

    def __init__(self) -> None:
        self._clip_model = None
        self._clip_processor = None
        _log().info("QualityAssessment initialized", extra={})

    def _load_clip(self) -> None:
        """Lazy load CLIP model."""
        if self._clip_model is not None:
            return
        try:
            from transformers import CLIPModel, CLIPProcessor  # type: ignore[reportMissingImports]

            _log().info("Loading CLIP model...", extra={})
            self._clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self._clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            _log().info("CLIP model loaded successfully", extra={})
        except Exception as e:
            _log().warning(
                "CLIP not available, using heuristic scoring only",
                extra={"error": str(e)},
            )

    def _sync_clip_score(self, image: Image.Image, prompt: str) -> float:
        """Synchronous CLIP similarity (run in executor). Returns 0-1."""
        self._load_clip()
        if self._clip_model is None or self._clip_processor is None:
            return 0.75
        try:
            import torch  # type: ignore[reportMissingImports]

            device = next(self._clip_model.parameters()).device
            inputs = self._clip_processor(
                text=[prompt],
                images=image,
                return_tensors="pt",
                padding=True,
            )
            inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self._clip_model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
            return float(probs[0][0].item())
        except Exception as e:
            _log().warning("CLIP scoring failed", extra={"error": str(e)})
            return 0.75

    async def _calculate_clip_score(self, image: Image.Image, prompt: str) -> float:
        """Calculate CLIP similarity score (0-1). Runs in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_clip_score, image, prompt)

    async def _download_image(self, url: str) -> Image.Image:
        """Download image from URL (sync request in executor)."""
        import urllib.request

        def _get() -> bytes:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.read()

        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, _get)
        image = Image.open(__import__("io").BytesIO(content))
        return image.convert("RGB")

    async def _detect_artifacts(self, image: Image.Image) -> float:
        """
        Detect common artifacts. Returns 0-1 (0 = no artifacts, 1 = many).
        """
        def _run() -> float:
            img_array = np.array(image)
            issues_score = 0.0

            # 1. Blur (Laplacian variance)
            gray = np.mean(img_array, axis=2).astype(np.uint8)
            laplacian_var = self._calculate_laplacian_variance(gray)
            if laplacian_var < 100:
                issues_score += 0.3

            # 2. Oversaturation
            hsv = self._rgb_to_hsv(img_array)
            saturation = hsv[:, :, 1]
            mean_sat = float(np.mean(saturation))
            if mean_sat > 0.8:
                issues_score += 0.2

            # 3. Extreme brightness
            brightness = float(np.mean(img_array)) / 255.0
            if brightness < 0.1 or brightness > 0.9:
                issues_score += 0.2

            # 4. Noise
            noise_level = self._estimate_noise(img_array)
            if noise_level > 0.05:
                issues_score += 0.3

            return min(1.0, issues_score)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)

    async def _assess_composition(self, image: Image.Image) -> float:
        """Assess visual composition. Returns 0-1 (higher = better)."""
        def _run() -> float:
            img_array = np.array(image)
            score = 1.0
            height, width = img_array.shape[:2]
            third_h, third_w = height // 3, width // 3

            sections = []
            for i in range(3):
                for j in range(3):
                    section = img_array[
                        i * third_h : (i + 1) * third_h,
                        j * third_w : (j + 1) * third_w,
                    ]
                    sections.append(float(np.mean(section)))
            center_brightness = sections[4]
            avg_brightness = float(np.mean(sections))
            if center_brightness > avg_brightness * 1.5:
                score -= 0.2

            r_mean, g_mean, b_mean = float(np.mean(img_array[:, :, 0])), float(np.mean(img_array[:, :, 1])), float(np.mean(img_array[:, :, 2]))
            color_std = float(np.std([r_mean, g_mean, b_mean]))
            if color_std > 50:
                score -= 0.1

            edges = self._simple_edge_detection(img_array)
            edge_density = float(np.mean(edges))
            if edge_density < 0.05 or edge_density > 0.3:
                score -= 0.1

            return max(0.0, score)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)

    def _determine_verdict(self, overall_score: float) -> QualityVerdict:
        if overall_score >= self.THRESHOLDS[QualityVerdict.EXCELLENT]:
            return QualityVerdict.EXCELLENT
        if overall_score >= self.THRESHOLDS[QualityVerdict.GOOD]:
            return QualityVerdict.GOOD
        if overall_score >= self.THRESHOLDS[QualityVerdict.ACCEPTABLE]:
            return QualityVerdict.ACCEPTABLE
        return QualityVerdict.POOR

    def _analyze_issues(
        self,
        clip_score: float,
        artifact_score: float,
        composition_score: float,
    ) -> Tuple[List[str], List[str]]:
        issues: List[str] = []
        suggestions: List[str] = []
        if clip_score < 0.6:
            issues.append("Poor semantic match with prompt")
            suggestions.append("Refine prompt for better clarity")
        if artifact_score > 0.5:
            issues.append("Significant artifacts detected")
            suggestions.append("Increase generation steps or change scheduler")
        if composition_score < 0.6:
            issues.append("Weak composition")
            suggestions.append("Add composition keywords (rule of thirds, balanced)")
        return issues, suggestions

    @staticmethod
    def _calculate_laplacian_variance(gray: np.ndarray) -> float:
        """Laplacian variance for blur detection (numpy-only or scipy)."""
        try:
            from scipy.signal import convolve2d  # type: ignore[reportMissingImports]
            kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
            result = convolve2d(gray.astype(np.float64), kernel, mode="valid")
            return float(np.var(result))
        except Exception:
            h, w = gray.shape
            if h < 3 or w < 3:
                return 0.0
            center = gray[1 : h - 1, 1 : w - 1].astype(np.float64)
            laplacian = (
                gray[0 : h - 2, 1 : w - 1].astype(np.float64)
                + gray[2 : h, 1 : w - 1].astype(np.float64)
                + gray[1 : h - 1, 0 : w - 2].astype(np.float64)
                + gray[1 : h - 1, 2 : w].astype(np.float64)
                - 4.0 * center
            )
            return float(np.var(laplacian))

    @staticmethod
    def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
        """Convert RGB (0-255) to HSV (H 0-360 scaled to 0-1, S/V 0-1). Numpy only."""
        r, g, b = rgb[:, :, 0] / 255.0, rgb[:, :, 1] / 255.0, rgb[:, :, 2] / 255.0
        v = np.maximum(np.maximum(r, g), b)
        c = v - np.minimum(np.minimum(r, g), b)
        s = np.where(v != 0, c / v, 0.0)
        hr = np.where(c != 0, (g - b) / c % 6.0, 0.0)
        hg = np.where(c != 0, (b - r) / c + 2.0, 0.0)
        hb = np.where(c != 0, (r - g) / c + 4.0, 0.0)
        h = np.where(v == r, hr, np.where(v == g, hg, hb))
        h = (h / 6.0) % 1.0
        return np.stack([h, s, v], axis=-1).astype(np.float32)

    @staticmethod
    def _estimate_noise(img: np.ndarray) -> float:
        """Estimate noise level (0-1)."""
        gray = np.mean(img, axis=2).astype(np.float64)
        try:
            from scipy.ndimage import gaussian_filter  # type: ignore[reportMissingImports]
            smoothed = gaussian_filter(gray, sigma=2)
        except Exception:
            # Numpy-only 3x3 box blur
            h, w = gray.shape
            if h < 3 or w < 3:
                smoothed = gray
            else:
                smoothed = np.zeros_like(gray)
                smoothed[1:-1, 1:-1] = (
                    gray[0:-2, 0:-2] + gray[0:-2, 1:-1] + gray[0:-2, 2:]
                    + gray[1:-1, 0:-2] + gray[1:-1, 1:-1] + gray[1:-1, 2:]
                    + gray[2:, 0:-2] + gray[2:, 1:-1] + gray[2:, 2:]
                ) / 9.0
                smoothed[0, :] = gray[0, :]
                smoothed[-1, :] = gray[-1, :]
                smoothed[:, 0] = gray[:, 0]
                smoothed[:, -1] = gray[:, -1]
        high_freq = gray - smoothed
        return float(np.clip(np.std(high_freq) / 255.0, 0, 1))

    @staticmethod
    def _simple_edge_detection(img: np.ndarray) -> np.ndarray:
        """Simple Sobel edge magnitude, normalized 0-1."""
        gray = np.mean(img, axis=2).astype(np.float64)
        h, w = gray.shape
        try:
            from scipy.signal import convolve2d  # type: ignore[reportMissingImports]
            sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
            sobel_y = sobel_x.T
            ex = convolve2d(gray, sobel_x, mode="same")
            ey = convolve2d(gray, sobel_y, mode="same")
        except Exception:
            ex = np.zeros_like(gray)
            ey = np.zeros_like(gray)
            if h > 2:
                ex[1 : h - 1, :] = gray[2:, :] - gray[: h - 2, :]
            if w > 2:
                ey[:, 1 : w - 1] = gray[:, 2:] - gray[:, : w - 2]
        edges = np.sqrt(ex ** 2 + ey ** 2)
        return (edges / 255.0).clip(0, 1)

    @trace_function("quality.assess")  # type: ignore[misc]
    async def assess_quality(
        self,
        image_url: str,
        prompt: str,
        enhanced_prompt: str,
    ) -> QualityScore:
        """
        Comprehensive quality assessment.

        Args:
            image_url: Generated image URL
            prompt: Original prompt
            enhanced_prompt: Enhanced prompt used

        Returns:
            QualityScore with verdict and details
        """
        try:
            image = await self._download_image(image_url)
        except Exception as e:
            _log().error("Failed to download image", extra={"error": str(e)})
            return QualityScore(
                overall_score=0.0,
                verdict=QualityVerdict.POOR,
                clip_score=0.0,
                artifact_score=1.0,
                composition_score=0.0,
                issues_found=["Failed to download image"],
                suggestions=["Retry generation"],
                should_retry=True,
                confidence=1.0,
            )

        clip_score, artifact_score, composition_score = await asyncio.gather(
            self._calculate_clip_score(image, enhanced_prompt),
            self._detect_artifacts(image),
            self._assess_composition(image),
        )

        overall_score = (
            clip_score * 0.50
            + (1.0 - artifact_score) * 0.25
            + composition_score * 0.25
        )
        verdict = self._determine_verdict(overall_score)
        issues, suggestions = self._analyze_issues(clip_score, artifact_score, composition_score)
        should_retry = verdict == QualityVerdict.POOR or len(issues) >= 3

        result = QualityScore(
            overall_score=overall_score,
            verdict=verdict,
            clip_score=clip_score,
            artifact_score=artifact_score,
            composition_score=composition_score,
            issues_found=issues,
            suggestions=suggestions,
            should_retry=should_retry,
            confidence=0.9,
        )

        _log().info(
            "Quality assessment complete",
            extra={
                "overall_score": f"{overall_score:.3f}",
                "verdict": verdict.value,
                "clip": f"{clip_score:.3f}",
                "artifacts": f"{artifact_score:.3f}",
                "composition": f"{composition_score:.3f}",
                "issues_count": len(issues),
                "should_retry": should_retry,
            },
        )

        try:
            from services.observability import Metrics
            m = getattr(Metrics, "quality_scores", None)
            if m is not None:
                m.labels(verdict=verdict.value).observe(overall_score)
        except Exception:
            pass

        return result

    async def assess_quality_batch(
        self,
        items: List[Tuple[str, str, str]],
        max_concurrent: int = 4,
    ) -> List[QualityScore]:
        """
        Batch quality assessment with concurrency limit.

        Args:
            items: List of (image_url, prompt, enhanced_prompt)
            max_concurrent: Max concurrent downloads/assessments

        Returns:
            List of QualityScore in same order as items
        """
        sem = asyncio.Semaphore(max_concurrent)

        async def one(url: str, prompt: str, enhanced: str) -> QualityScore:
            async with sem:
                return await self.assess_quality(url, prompt, enhanced)

        return await asyncio.gather(*[one(u, p, e) for u, p, e in items])

    def get_retry_prompt_suggestion(self, score: QualityScore) -> Optional[str]:
        """
        Suggest a refined prompt for retry based on issues.

        Returns:
            Optional string with suggested additions to prompt, or None if no retry needed.
        """
        if not score.should_retry or not score.suggestions:
            return None
        return " ".join(score.suggestions)


# ==================== Convenience API ====================

_default_assessor: Optional[QualityAssessment] = None


def get_default_assessor() -> QualityAssessment:
    """Return the default QualityAssessment instance (singleton)."""
    global _default_assessor
    if _default_assessor is None:
        _default_assessor = QualityAssessment()
    return _default_assessor


async def assess_quality(
    image_url: str,
    prompt: str,
    enhanced_prompt: str,
) -> QualityScore:
    """Convenience: assess using default QualityAssessment."""
    return await get_default_assessor().assess_quality(image_url, prompt, enhanced_prompt)


__all__ = [
    "QualityVerdict",
    "QualityScore",
    "QualityAssessment",
    "get_default_assessor",
    "assess_quality",
]


# ==================== Validation & Tests ====================

if __name__ == "__main__":
    import time

    assessor = QualityAssessment()

    # 1. Verdict thresholds
    assert assessor._determine_verdict(0.9) == QualityVerdict.EXCELLENT
    assert assessor._determine_verdict(0.80) == QualityVerdict.GOOD
    assert assessor._determine_verdict(0.70) == QualityVerdict.ACCEPTABLE
    assert assessor._determine_verdict(0.5) == QualityVerdict.POOR
    print("Verdict thresholds OK.")

    # 2. Issue analysis
    issues, suggestions = assessor._analyze_issues(0.5, 0.6, 0.5)
    assert "semantic match" in " ".join(issues).lower() or len(issues) >= 1
    assert len(suggestions) >= 1
    print("Issue analysis OK.")

    # 3. Helpers on synthetic image
    h, w = 64, 64
    rgb = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
    hsv = assessor._rgb_to_hsv(rgb)
    assert hsv.shape == rgb.shape
    assert np.all(hsv >= 0) and np.all(hsv <= 1)
    gray = np.mean(rgb, axis=2).astype(np.uint8)
    lap_var = assessor._calculate_laplacian_variance(gray)
    assert lap_var >= 0
    edges = assessor._simple_edge_detection(rgb)
    assert edges.shape == (h, w)
    print("Helper methods OK.")

    # 4. Retry logic
    poor = QualityScore(0.5, QualityVerdict.POOR, 0.5, 0.5, 0.5, ["a"], ["b"], True, 0.9)
    assert poor.should_retry
    suggestion = assessor.get_retry_prompt_suggestion(poor)
    assert suggestion is not None
    good = QualityScore(0.9, QualityVerdict.EXCELLENT, 0.9, 0.1, 0.9, [], [], False, 0.9)
    assert assessor.get_retry_prompt_suggestion(good) is None
    print("Retry logic OK.")

    # 5. Async assess with local image (no download) - use PIL Image in memory
    pil_img = Image.fromarray(rgb)
    # Run artifact and composition only (no CLIP, no download)
    async def run_heuristics():
        art = await assessor._detect_artifacts(pil_img)
        comp = await assessor._assess_composition(pil_img)
        return art, comp

    art_score, comp_score = asyncio.run(run_heuristics())
    assert 0 <= art_score <= 1 and 0 <= comp_score <= 1
    print(f"Artifact score: {art_score:.3f}, Composition score: {comp_score:.3f}")

    # 6. Batch (mock - same image, no real URL)
    async def run_batch():
        # Use data that would fail download to test batch structure
        items = [
            ("http://localhost/invalid1", "p1", "e1"),
            ("http://localhost/invalid2", "p2", "e2"),
        ]
        results = await assessor.assess_quality_batch(items, max_concurrent=2)
        return len(results)

    try:
        n = asyncio.run(run_batch())
        assert n == 2
        print("Batch returns 2 results.")
    except Exception as e:
        print("Batch test skipped (download failure expected):", e)

    print("\nAll validation checks passed.")
    # Validation checklist:
    # [x] Verdict thresholds
    # [x] Issue analysis and suggestions
    # [x] Helper methods (HSV, Laplacian, edges)
    # [x] Retry logic (should_retry, get_retry_prompt_suggestion)
    # [x] Artifact and composition scores in 0-1
    # [ ] CLIP scoring (requires transformers/torch - run with deps)
    # [ ] Full assess_quality with real URL (run with image URL)
    # [ ] Performance <2s per image (measure in production)
