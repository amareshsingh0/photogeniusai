"""
Issue Analyzer - Determines what went wrong and how to fix it.

Analyzes validation results and decides:
1. What type of fix is needed (inpaint, regenerate, adjust params)
2. Which regions need fixing
3. What parameters to change for next iteration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class IssueFix:
    """Represents a specific fix to apply."""

    fix_type: str  # 'inpaint', 'regenerate', 'adjust_params', 'adjust_camera'
    severity: str  # 'critical', 'high', 'medium', 'low'
    issue_category: str  # 'anatomy', 'physics', 'count', 'occlusion'
    target_region: Optional[Tuple[int, int, int, int]] = None  # bbox (x1, y1, x2, y2)
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher = more important

    def __post_init__(self) -> None:
        if self.parameters is None:
            self.parameters = {}

        # Auto-set priority from severity
        severity_priority = {
            "critical": 100,
            "high": 75,
            "medium": 50,
            "low": 25,
        }
        if self.priority == 0:
            self.priority = severity_priority.get(self.severity, 50)


class IssueAnalyzer:
    """
    Analyze validation failures and determine fixes.

    Strategies:
    1. Person count mismatch → Regenerate with stronger ControlNet
    2. Occluded faces → Adjust camera angle
    3. Malformed hands → Inpaint hand regions
    4. Merged bodies → Regenerate with increased spacing
    5. Physics issues → Regenerate with stronger physics prompts
    """

    def __init__(self) -> None:
        self.fix_history: List[Dict[str, Any]] = []  # Track fixes attempted

    def analyze_and_plan_fixes(
        self,
        validation_result: Any,
        scene_graph: Dict[str, Any],
        iteration: int,
        max_iterations: int,
    ) -> List[IssueFix]:
        """
        Analyze validation result and plan fixes.

        Args:
            validation_result: AnatomyValidationResult from TriModelValidator.validate_anatomy
            scene_graph: Scene graph with layout/constraints
            iteration: Current iteration number (0-indexed)
            max_iterations: Maximum allowed iterations

        Returns:
            List of IssueFix objects, sorted by priority
        """
        fixes: List[IssueFix] = []

        score = getattr(validation_result, "overall_score", 0.0)

        if iteration >= max_iterations - 1:
            fixes = self._plan_critical_fixes_only(validation_result)
        elif score < 0.4:
            fixes = self._plan_full_regeneration(validation_result, scene_graph)
        elif score < 0.7:
            fixes = self._plan_major_fixes(validation_result, scene_graph)
        else:
            fixes = self._plan_targeted_fixes(validation_result)

        fixes.sort(key=lambda f: f.priority, reverse=True)
        return fixes

    def _plan_critical_fixes_only(self, validation_result: Any) -> List[IssueFix]:
        """Plan only critical fixes (last iteration)."""
        fixes: List[IssueFix] = []
        issues = getattr(validation_result, "issues", [])
        for issue in issues:
            if issue.get("severity") == "critical":
                fix = self._issue_to_fix(issue)
                if fix:
                    fixes.append(fix)
        return fixes

    def _plan_full_regeneration(
        self,
        validation_result: Any,
        scene_graph: Dict[str, Any],
    ) -> List[IssueFix]:
        """Plan full regeneration with scene adjustments."""
        fixes: List[IssueFix] = []
        metadata = getattr(validation_result, "metadata", {}) or {}
        expected_people = metadata.get("expected_people", 0)
        yolo_count = metadata.get("yolo_count", 0)

        if abs(yolo_count - expected_people) >= 2:
            fixes.append(
                IssueFix(
                    fix_type="regenerate",
                    severity="critical",
                    issue_category="count",
                    parameters={
                        "reason": "major_person_count_mismatch",
                        "increase_openpose_weight": 0.95,
                        "increase_guidance_scale": 8.5,
                        "adjust_spacing": True,
                    },
                )
            )

        face_count = metadata.get("face_count", 0)
        if expected_people > 0 and face_count < expected_people - 1:
            fixes.append(
                IssueFix(
                    fix_type="adjust_camera",
                    severity="critical",
                    issue_category="occlusion",
                    parameters={
                        "reason": "multiple_occluded_faces",
                        "camera_tilt": -8,
                        "camera_height": "+10%",
                        "increase_fov": 5,
                    },
                )
            )

        seg_count = metadata.get("segmentation_count", 0)
        if expected_people > 1 and seg_count < expected_people:
            fixes.append(
                IssueFix(
                    fix_type="regenerate",
                    severity="critical",
                    issue_category="anatomy",
                    parameters={
                        "reason": "merged_bodies",
                        "increase_person_spacing": 1.5,
                        "stronger_segmentation": True,
                    },
                )
            )

        return fixes

    def _plan_major_fixes(
        self,
        validation_result: Any,
        scene_graph: Dict[str, Any],
    ) -> List[IssueFix]:
        """Plan major fixes (score 0.4-0.7)."""
        fixes: List[IssueFix] = []
        issues = getattr(validation_result, "issues", [])
        for issue in issues:
            if issue.get("severity") in ("critical", "high"):
                fix = self._issue_to_fix(issue)
                if fix:
                    fixes.append(fix)

        scores = getattr(validation_result, "scores", {}) or {}
        if scores.get("hands", 1.0) < 0.6:
            fixes.append(
                IssueFix(
                    fix_type="inpaint",
                    severity="high",
                    issue_category="anatomy",
                    parameters={
                        "reason": "poor_hand_anatomy",
                        "target": "hands",
                        "inpaint_strength": 0.7,
                    },
                )
            )

        if scores.get("faces", 1.0) < 0.7:
            fixes.append(
                IssueFix(
                    fix_type="regenerate",
                    severity="high",
                    issue_category="occlusion",
                    parameters={
                        "reason": "face_visibility_issues",
                        "camera_tilt": -5,
                        "ensure_heads_visible": True,
                    },
                )
            )

        return fixes

    def _plan_targeted_fixes(self, validation_result: Any) -> List[IssueFix]:
        """Plan targeted fixes (score 0.7-0.85)."""
        fixes: List[IssueFix] = []
        issues = getattr(validation_result, "issues", [])
        for issue in issues:
            if issue.get("severity") in ("medium", "high"):
                fix = self._issue_to_fix(issue)
                if fix:
                    if fix.fix_type == "regenerate":
                        fix.fix_type = "inpaint"
                        fix.parameters["use_inpaint"] = True
                    fixes.append(fix)
        return fixes

    def _issue_to_fix(self, issue: Dict[str, Any]) -> Optional[IssueFix]:
        """Convert an issue dict to an IssueFix."""
        issue_type = issue.get("type", "")
        severity = issue.get("severity", "medium")

        if issue_type == "person_count":
            return IssueFix(
                fix_type="regenerate",
                severity=severity,
                issue_category="count",
                parameters={
                    "reason": "person_count_mismatch",
                    "expected": issue.get("expected"),
                    "detected": issue.get("detected_yolo"),
                    "adjust_controlnet_weight": 0.95,
                },
            )

        if issue_type == "face_count":
            return IssueFix(
                fix_type="adjust_camera",
                severity=severity,
                issue_category="occlusion",
                parameters={
                    "reason": "faces_occluded",
                    "expected": issue.get("expected"),
                    "detected": issue.get("detected"),
                    "camera_tilt": -6,
                },
            )

        if issue_type == "hand_anatomy":
            return IssueFix(
                fix_type="inpaint",
                severity=severity,
                issue_category="anatomy",
                parameters={
                    "reason": "malformed_hands",
                    "invalid_hands": issue.get("invalid_hands"),
                    "target_region": "hands",
                },
            )

        if issue_type == "body_separation":
            return IssueFix(
                fix_type="regenerate",
                severity=severity,
                issue_category="anatomy",
                parameters={
                    "reason": "merged_bodies",
                    "expected": issue.get("expected"),
                    "detected": issue.get("detected"),
                    "increase_spacing": 1.3,
                },
            )

        return None

    def record_iteration(self, score: float, fixes: List[IssueFix]) -> None:
        """Record an iteration for progress tracking (used by should_continue_refining)."""
        self.fix_history.append({"score": score, "fixes": fixes})

    def should_continue_refining(
        self,
        validation_result: Any,
        iteration: int,
        max_iterations: int,
        score_threshold: float = 0.85,
    ) -> bool:
        """
        Decide if we should continue refining.

        Continue if:
        - Score below threshold AND
        - Haven't hit max iterations AND
        - Score is improving (not stuck)
        """
        if iteration >= max_iterations:
            return False

        score = getattr(validation_result, "overall_score", 0.0)
        if score >= score_threshold:
            return False

        if len(self.fix_history) >= 2:
            prev_score = self.fix_history[-2].get("score", 0.0)
            curr_score = score
            if curr_score <= prev_score + 0.05:
                if iteration >= max_iterations // 2:
                    return False

        return True
