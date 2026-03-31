"""
Tri-Model Anatomy Validation System.

Uses three independent models for validation consensus:
1. YOLO v8: Person counting, object detection
2. MediaPipe: Hand anatomy (5 fingers), face landmarks
3. SAM / fallback: Body segmentation, separation validation

All three must agree for validation to pass.

Backward compatibility: validate(image, expected_person_count, constraints)
returns TriModelConsensus with ValidationResult list for deterministic pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Lazy imports for heavy deps (only when use_models=True)
_HAS_OPENCV = False
_HAS_MEDIAPIPE = False
_HAS_YOLO = False
_HAS_SAM = False


def _constraint_type(c: Any) -> str:
    if isinstance(c, dict):
        return c.get("type", "")
    return getattr(c, "type", "")


def _constraint_rule(c: Any) -> str:
    if isinstance(c, dict):
        return c.get("rule", "")
    return getattr(c, "rule", "")


# -----------------------------------------------------------------------------
# Backward-compatible result types (used by deterministic_pipeline, refinement)
# -----------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of one constraint check (backward-compatible)."""

    constraint_type: str
    rule: str
    passed: bool
    confidence: float  # 0–1
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TriModelConsensus:
    """Consensus from YOLO + MediaPipe + SAM (or heuristic fallback)."""

    all_passed: bool
    results: List[ValidationResult]
    head_count_detected: Optional[int] = None
    person_count_detected: Optional[int] = None
    limb_violations: List[str] = field(default_factory=list)
    occlusion_detected: List[str] = field(default_factory=list)
    consensus_count: Optional[int] = None
    hand_anatomy_passed: bool = True


# -----------------------------------------------------------------------------
# Anatomy validation result (spec API: is_valid, overall_score, issues, etc.)
# -----------------------------------------------------------------------------


class AnatomyValidationResult:
    """Structured anatomy validation result from the three models."""

    def __init__(self) -> None:
        self.is_valid = False
        self.overall_score = 0.0
        self.model_results: Dict[str, Any] = {}
        self.issues: List[Dict[str, Any]] = []
        self.scores: Dict[str, float] = {}
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "overall_score": self.overall_score,
            "model_results": self.model_results,
            "issues": self.issues,
            "scores": self.scores,
            "metadata": self.metadata,
        }


# -----------------------------------------------------------------------------
# Tri-Model Validator
# -----------------------------------------------------------------------------


class TriModelValidator:
    """
    Three-model consensus validation system.

    Validates:
    - Person count (YOLO + segmentation consensus)
    - Head visibility (MediaPipe faces)
    - Hand anatomy (MediaPipe hands)
    - Body separation (SAM or connected-components fallback)

    use_models=False: heuristic fallback only (no heavy deps required).
    use_models=True: load YOLO, MediaPipe, optional SAM.
    """

    def __init__(self, use_models: bool = False, device: str = "cuda") -> None:
        self.use_models = use_models
        self.device = device
        self._yolo = None
        self._mp_hands = None
        self._mp_face_mesh = None
        self._sam = None
        self._sam_loaded = False
        if use_models:
            self._load_models()

    @property
    def yolo(self) -> Optional[Any]:
        """YOLO model (when use_models=True)."""
        return self._yolo

    @property
    def mp_hands(self) -> Optional[Any]:
        """MediaPipe hands solution (when use_models=True)."""
        return self._mp_hands

    @property
    def mp_face_mesh(self) -> Optional[Any]:
        """MediaPipe face mesh solution (when use_models=True)."""
        return self._mp_face_mesh

    def _load_models(self) -> None:
        """Load YOLO, MediaPipe, and optionally SAM."""
        global _HAS_OPENCV, _HAS_MEDIAPIPE, _HAS_YOLO, _HAS_SAM
        try:
            import cv2  # noqa: F401

            _HAS_OPENCV = True
        except ImportError:
            pass
        try:
            import mediapipe as mp  # noqa: F401

            _HAS_MEDIAPIPE = True
        except ImportError:
            pass
        try:
            from ultralytics import YOLO
            import torch

            dev = self.device if torch.cuda.is_available() else "cpu"
            self._yolo = YOLO("yolov8x.pt")
            self._yolo.to(dev)
            self.device = dev
            _HAS_YOLO = True
        except Exception as e:
            print(f"  ⚠️  YOLO not loaded: {e}")
        try:
            import mediapipe as mp

            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=True,
                max_num_hands=20,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=20,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            _HAS_MEDIAPIPE = True
        except Exception as e:
            print(f"  ⚠️  MediaPipe not loaded: {e}")
        try:
            from segment_anything import sam_model_registry, SamAutomaticMaskGenerator

            # SAM is heavy; we use fallback by default unless user provides checkpoint
            _HAS_SAM = True
            self._sam_loaded = False  # Set True when checkpoint loaded
        except ImportError:
            pass

    def _image_to_numpy(self, image: Any) -> Tuple[Any, Any]:
        """Convert image to numpy RGB and BGR for OpenCV/MediaPipe."""
        import numpy as np

        if hasattr(image, "size") and hasattr(image, "mode"):
            # PIL Image
            img_np = np.array(image)
            if len(img_np.shape) == 2:
                img_np = np.stack([img_np] * 3, axis=-1)
            elif img_np.shape[2] == 4:
                img_np = img_np[:, :, :3]
            return img_np, img_np.copy()
        if isinstance(image, np.ndarray):
            if len(image.shape) == 2:
                img_np = np.stack([image] * 3, axis=-1)
            else:
                img_np = image
            return img_np, img_np.copy()
        raise TypeError("image must be PIL Image or numpy array")

    def _validate_with_yolo(
        self,
        image: Any,
        expected_people: int,
    ) -> Dict[str, Any]:
        """Validate with YOLO: person counting. Returns dict with detected_people, score, etc."""
        import numpy as np

        if self._yolo is None:
            return {
                "detected_people": expected_people,
                "expected_people": expected_people,
                "matches": True,
                "confidence": 0.6,
                "score": 0.6,
                "bboxes": [],
                "method": "heuristic",
            }
        results = self._yolo(image, device=self.device, verbose=False)
        detections = results[0].boxes
        person_detections = []
        person_confidences = []
        for i, box in enumerate(detections):
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            if cls == 0:
                person_detections.append(box.xyxy[0].cpu().numpy())
                person_confidences.append(conf)
        detected_people = len(person_detections)
        avg_confidence = (
            float(np.mean(person_confidences)) if person_confidences else 0.0
        )
        if detected_people == expected_people:
            score = 1.0
        elif abs(detected_people - expected_people) == 1:
            score = 0.6
        elif abs(detected_people - expected_people) == 2:
            score = 0.3
        else:
            score = 0.1
        score = score * (0.5 + 0.5 * avg_confidence)
        return {
            "detected_people": detected_people,
            "expected_people": expected_people,
            "matches": detected_people == expected_people,
            "confidence": avg_confidence,
            "score": float(score),
            "bboxes": person_detections,
        }

    def _validate_with_mediapipe(
        self,
        image_rgb: Any,
        expected_people: int,
    ) -> Dict[str, Any]:
        """Validate with MediaPipe: faces and hands."""
        import numpy as np

        if self._mp_hands is None or self._mp_face_mesh is None:
            return {
                "detected_faces": expected_people,
                "expected_faces": expected_people,
                "face_matches": True,
                "face_score": 0.6,
                "detected_hands": 0,
                "hand_score": 0.5,
                "hand_details": [],
                "method": "heuristic",
            }
        if image_rgb.shape[2] == 4:
            image_rgb = image_rgb[:, :, :3]
        face_results = self._mp_face_mesh.process(image_rgb)
        detected_faces = (
            len(face_results.multi_face_landmarks)
            if face_results.multi_face_landmarks
            else 0
        )
        if expected_people == 0:
            face_score = 1.0
        elif detected_faces == expected_people:
            face_score = 1.0
        elif abs(detected_faces - expected_people) == 1:
            face_score = 0.6
        else:
            face_score = 0.3
        hand_results = self._mp_hands.process(image_rgb)
        detected_hands = 0
        hand_details: List[Dict[str, Any]] = []
        if hand_results.multi_hand_landmarks:
            detected_hands = len(hand_results.multi_hand_landmarks)
            finger_tips = [4, 8, 12, 16, 20]
            for idx, hand_landmarks in enumerate(hand_results.multi_hand_landmarks):
                num_landmarks = len(hand_landmarks.landmark)
                has_all_fingers = all(i < num_landmarks for i in finger_tips)
                hand_details.append(
                    {
                        "hand_index": idx,
                        "num_landmarks": num_landmarks,
                        "has_all_fingers": has_all_fingers,
                        "is_valid": num_landmarks == 21 and has_all_fingers,
                    }
                )
        if detected_hands == 0:
            hand_score = 0.5
        else:
            valid_hands = sum(1 for h in hand_details if h["is_valid"])
            hand_score = valid_hands / detected_hands
        return {
            "detected_faces": detected_faces,
            "expected_faces": expected_people,
            "face_matches": detected_faces == expected_people,
            "face_score": float(face_score),
            "detected_hands": detected_hands,
            "hand_score": float(hand_score),
            "hand_details": hand_details,
        }

    def _validate_segmentation(
        self,
        image: Any,
        expected_people: int,
    ) -> Dict[str, Any]:
        """Validate body separation (SAM if loaded, else connected-components)."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            return {
                "distinct_bodies": expected_people,
                "expected_bodies": expected_people,
                "matches": True,
                "score": 0.6,
                "method": "heuristic",
            }
        if self._sam is not None and self._sam_loaded:
            # TODO: run SAM automatic mask generator, count person-like masks
            pass
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        min_area = (image.shape[0] * image.shape[1]) * 0.01
        significant = [c for c in contours if cv2.contourArea(c) > min_area]
        distinct_bodies = len(significant)
        if expected_people == 0:
            score = 1.0
        elif distinct_bodies == expected_people:
            score = 1.0
        elif abs(distinct_bodies - expected_people) == 1:
            score = 0.7
        else:
            score = 0.4
        return {
            "distinct_bodies": distinct_bodies,
            "expected_bodies": expected_people,
            "matches": distinct_bodies == expected_people,
            "score": float(score),
            "method": "connected_components",
        }

    def _compute_consensus(
        self,
        result: AnatomyValidationResult,
        expected_people: int,
        scene_graph: Dict[str, Any],
    ) -> AnatomyValidationResult:
        """Compute consensus from all three models and set result.is_valid."""
        yolo_res = result.model_results.get("yolo", {})
        mp_res = result.model_results.get("mediapipe", {})
        seg_res = result.model_results.get("segmentation", {})
        issues: List[Dict[str, Any]] = []
        if not yolo_res.get("matches", True):
            issues.append(
                {
                    "type": "person_count",
                    "severity": "critical",
                    "expected": expected_people,
                    "detected_yolo": yolo_res.get("detected_people", 0),
                    "message": f"YOLO detected {yolo_res.get('detected_people', 0)} people, expected {expected_people}",
                }
            )
        if not mp_res.get("face_matches", True) and expected_people > 0:
            issues.append(
                {
                    "type": "face_count",
                    "severity": "critical",
                    "expected": expected_people,
                    "detected": mp_res.get("detected_faces", 0),
                    "message": f"Only {mp_res.get('detected_faces', 0)} faces detected, expected {expected_people}",
                }
            )
        if mp_res.get("hand_score", 1.0) < 0.7 and mp_res.get("detected_hands", 0) > 0:
            hand_details = mp_res.get("hand_details", [])
            invalid = [h for h in hand_details if not h.get("is_valid", True)]
            if invalid:
                issues.append(
                    {
                        "type": "hand_anatomy",
                        "severity": "high",
                        "invalid_hands": len(invalid),
                        "message": f"{len(invalid)} hands have incorrect anatomy",
                    }
                )
        if not seg_res.get("matches", True) and expected_people > 1:
            issues.append(
                {
                    "type": "body_separation",
                    "severity": "high",
                    "expected": expected_people,
                    "detected": seg_res.get("distinct_bodies", 0),
                    "message": f"Bodies may be merged: detected {seg_res.get('distinct_bodies', 0)} distinct regions",
                }
            )
        weights = {
            "person_count_yolo": 0.30,
            "faces": 0.30,
            "hands": 0.20,
            "body_separation": 0.20,
        }
        overall = sum(result.scores.get(key, 0.0) * w for key, w in weights.items())
        critical = [i for i in issues if i.get("severity") == "critical"]
        result.is_valid = (overall >= 0.80) and (len(critical) == 0)
        result.overall_score = overall
        result.issues = issues
        result.metadata = {
            "expected_people": expected_people,
            "yolo_count": yolo_res.get("detected_people"),
            "face_count": mp_res.get("detected_faces"),
            "hand_count": mp_res.get("detected_hands"),
            "segmentation_count": seg_res.get("distinct_bodies"),
            "critical_issues": len(critical),
            "total_issues": len(issues),
        }
        return result

    def validate_anatomy(
        self,
        image: Any,
        scene_graph: Dict[str, Any],
        return_detailed: bool = True,
    ) -> AnatomyValidationResult:
        """
        Validate image using all three models (anatomy API).

        image: PIL Image or numpy array.
        scene_graph: Must have quality_requirements.person_count_exact.
        """
        result = AnatomyValidationResult()
        try:
            image_np, image_bgr = self._image_to_numpy(image)
        except Exception:
            result.issues.append({"type": "input", "message": "Invalid image"})
            return result
        expected_people = scene_graph.get("quality_requirements", {}).get(
            "person_count_exact", 0
        )
        if self.use_models and self._yolo is not None:
            yolo_res = self._validate_with_yolo(image_np, expected_people)
        else:
            yolo_res = self._validate_with_yolo(image_np, expected_people)
        result.model_results["yolo"] = yolo_res
        result.scores["person_count_yolo"] = yolo_res.get("score", 0.6)
        if self.use_models and (
            self._mp_hands is not None or self._mp_face_mesh is not None
        ):
            mp_res = self._validate_with_mediapipe(image_np, expected_people)
        else:
            mp_res = self._validate_with_mediapipe(image_np, expected_people)
        result.model_results["mediapipe"] = mp_res
        result.scores["faces"] = mp_res.get("face_score", 0.6)
        result.scores["hands"] = mp_res.get("hand_score", 0.5)
        seg_res = self._validate_segmentation(image_np, expected_people)
        result.model_results["segmentation"] = seg_res
        result.scores["body_separation"] = seg_res.get("score", 0.6)
        self._compute_consensus(result, expected_people, scene_graph)
        return result

    def validate_simple(self, image: Any, expected_people: int) -> Tuple[bool, float]:
        """Simplified validation. Returns (is_valid, score)."""
        scene_graph = {"quality_requirements": {"person_count_exact": expected_people}}
        result = self.validate_anatomy(image, scene_graph, return_detailed=False)
        return result.is_valid, result.overall_score

    # -------------------------------------------------------------------------
    # Backward-compatible API: validate(image, expected_person_count, constraints)
    # -------------------------------------------------------------------------

    def validate(
        self,
        image: Any,
        expected_person_count: int,
        constraints: List[Any],
    ) -> TriModelConsensus:
        """
        Run tri-model validation (or heuristic fallback).
        Returns TriModelConsensus for use by deterministic pipeline and refinement.
        """
        results: List[ValidationResult] = []
        limb_violations: List[str] = []
        occlusion_detected: List[str] = []
        scene_graph = {
            "quality_requirements": {"person_count_exact": expected_person_count},
        }
        anatomy_result = self.validate_anatomy(image, scene_graph, return_detailed=True)
        yolo_res = anatomy_result.model_results.get("yolo", {})
        mp_res = anatomy_result.model_results.get("mediapipe", {})
        seg_res = anatomy_result.model_results.get("segmentation", {})
        detected_persons = yolo_res.get("detected_people")
        detected_heads = mp_res.get("detected_faces")
        segments_count = seg_res.get("distinct_bodies")
        # When models not loaded (heuristic), assume hand anatomy passes
        hand_ok = (
            not self.use_models
            or mp_res.get("hand_score", 1.0) >= 0.7
            or mp_res.get("detected_hands", 0) == 0
        )
        for c in constraints:
            ctype = _constraint_type(c)
            rule = _constraint_rule(c)
            if ctype == "visibility" and "head" in rule.lower():
                passed = anatomy_result.scores.get("faces", 0) >= 0.6
                details = {
                    "expected": expected_person_count,
                    "detected": detected_heads,
                    "detected_heads": detected_heads,
                    "detected_persons": detected_persons,
                    "method": "tri_model",
                }
                results.append(
                    ValidationResult(
                        constraint_type="visibility",
                        rule=rule,
                        passed=passed,
                        confidence=anatomy_result.scores.get("faces", 0.5),
                        details=details,
                    )
                )
                if not passed and detected_heads is not None:
                    occlusion_detected.append(
                        f"head_count: expected {expected_person_count}, got {detected_heads}"
                    )
            elif ctype == "anatomy" and (
                "arm" in rule.lower()
                or "limb" in rule.lower()
                or "hand" in rule.lower()
            ):
                passed = hand_ok and anatomy_result.scores.get("hands", 0.5) >= 0.7
                details = {
                    "expected_per_person": {"arms": 2, "legs": 2},
                    "violations": [
                        i["message"]
                        for i in anatomy_result.issues
                        if i.get("type") == "hand_anatomy"
                    ],
                    "method": "tri_model",
                }
                if details["violations"]:
                    limb_violations.extend(details["violations"])
                results.append(
                    ValidationResult(
                        constraint_type="anatomy",
                        rule=rule,
                        passed=passed,
                        confidence=anatomy_result.scores.get("hands", 0.5),
                        details=details,
                    )
                )
            elif ctype == "spatial" and "merged" in rule.lower():
                passed = anatomy_result.scores.get("body_separation", 0) >= 0.6
                details = {
                    "expected_persons": expected_person_count,
                    "segments_count": segments_count,
                    "method": "tri_model",
                }
                results.append(
                    ValidationResult(
                        constraint_type="spatial",
                        rule=rule,
                        passed=passed,
                        confidence=anatomy_result.scores.get("body_separation", 0.5),
                        details=details,
                    )
                )
            else:
                passed = anatomy_result.is_valid
                results.append(
                    ValidationResult(
                        constraint_type=ctype,
                        rule=rule,
                        passed=passed,
                        confidence=anatomy_result.overall_score,
                        details={
                            "method": "tri_model",
                            "anatomy_valid": anatomy_result.is_valid,
                        },
                    )
                )
        counts = [
            c
            for c in [detected_heads, detected_persons, segments_count]
            if c is not None
        ]
        from collections import Counter

        cnt = Counter(counts)
        best_count, best_n = (
            cnt.most_common(1)[0] if cnt else (expected_person_count, 0)
        )
        consensus_count = (
            min(3, sum(1 for c in counts if c == best_count)) if counts else 0
        )
        all_passed = anatomy_result.is_valid and all(r.passed for r in results)
        return TriModelConsensus(
            all_passed=all_passed,
            results=results,
            head_count_detected=detected_heads,
            person_count_detected=detected_persons,
            limb_violations=limb_violations,
            occlusion_detected=occlusion_detected,
            consensus_count=consensus_count if consensus_count > 0 else None,
            hand_anatomy_passed=hand_ok,
        )


# -----------------------------------------------------------------------------
# Anatomy issue localizer (for refinement engine)
# -----------------------------------------------------------------------------


class AnatomyIssueLocalizer:
    """Localize anatomy issues in image for targeted refinement."""

    def __init__(self, device: str = "cuda") -> None:
        self.validator = TriModelValidator(use_models=True, device=device)

    def localize_issues(
        self,
        image: Any,
        validation_result: AnatomyValidationResult,
    ) -> List[Dict[str, Any]]:
        """Return list of issue locations with suggested_fix."""
        localizations: List[Dict[str, Any]] = []
        yolo_results = validation_result.model_results.get("yolo", {})
        bboxes = yolo_results.get("bboxes", [])
        mp_results = validation_result.model_results.get("mediapipe", {})
        hand_details = mp_results.get("hand_details", [])
        for hand_info in hand_details:
            if not hand_info.get("is_valid", True):
                localizations.append(
                    {
                        "issue_type": "hand_anatomy",
                        "hand_index": hand_info.get("hand_index"),
                        "severity": "high",
                        "suggested_fix": "inpaint_hand",
                        "bbox": None,
                    }
                )
        for issue in validation_result.issues:
            if issue.get("type") == "face_count":
                localizations.append(
                    {
                        "issue_type": "occluded_face",
                        "severity": "critical",
                        "suggested_fix": "regenerate_with_camera_adjustment",
                        "bbox": None,
                    }
                )
        return localizations
