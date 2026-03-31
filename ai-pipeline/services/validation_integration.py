"""
Integration layer between validation and refinement.

Provides utilities for:
- Running validation on generated images
- Deciding if refinement is needed
- Extracting actionable feedback
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

from .tri_model_validator import (
    AnatomyValidationResult,
    TriModelValidator,
)


class ValidationIntegration:
    """
    Integrate validation into generation pipeline.

    Usage:
        integration = ValidationIntegration()
        should_refine, feedback = integration.check_and_decide(image, scene_graph)
    """

    def __init__(
        self,
        use_models: bool = False,
        device: str = "cuda",
        quality_threshold: float = 0.85,
    ) -> None:
        self.validator = TriModelValidator(use_models=use_models, device=device)
        self.quality_threshold = quality_threshold

    def check_and_decide(
        self,
        image: Any,
        scene_graph: Dict[str, Any],
        threshold: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate image and decide if refinement needed.

        Args:
            image: Generated image (PIL Image or numpy array)
            scene_graph: Scene requirements (must have quality_requirements.person_count_exact)
            threshold: Quality threshold (default 0.85)

        Returns:
            (should_refine, feedback_dict)

            where feedback_dict contains:
            {
                'validation_result': AnatomyValidationResult,
                'refinement_priority': 'high' | 'medium' | 'low',
                'suggested_fixes': [...],
                'quality_score': float,
                'issues_count': int,
            }
        """
        threshold = threshold or self.quality_threshold

        result = self.validator.validate_anatomy(
            image, scene_graph, return_detailed=True
        )

        should_refine = not result.is_valid or result.overall_score < threshold

        if result.overall_score < 0.5:
            priority = "high"
        elif result.overall_score < threshold:
            priority = "medium"
        else:
            priority = "low"

        suggested_fixes = self._extract_fixes(result)

        feedback: Dict[str, Any] = {
            "validation_result": result,
            "refinement_priority": priority,
            "suggested_fixes": suggested_fixes,
            "quality_score": result.overall_score,
            "issues_count": len(result.issues),
        }

        return should_refine, feedback

    def _extract_fixes(self, result: AnatomyValidationResult) -> List[Dict[str, Any]]:
        """Extract actionable fixes from validation result."""
        fixes: List[Dict[str, Any]] = []

        for issue in result.issues:
            issue_type = issue.get("type", "")

            if issue_type == "person_count":
                fixes.append(
                    {
                        "type": "regenerate",
                        "reason": "incorrect_person_count",
                        "severity": issue.get("severity", "critical"),
                        "details": issue,
                    }
                )

            elif issue_type == "face_count":
                fixes.append(
                    {
                        "type": "camera_adjustment",
                        "reason": "occluded_faces",
                        "severity": issue.get("severity", "critical"),
                        "action": "tilt_camera_to_reveal_faces",
                    }
                )

            elif issue_type == "hand_anatomy":
                fixes.append(
                    {
                        "type": "inpaint",
                        "reason": "malformed_hands",
                        "severity": issue.get("severity", "high"),
                        "action": "inpaint_hand_regions",
                    }
                )

            elif issue_type == "body_separation":
                fixes.append(
                    {
                        "type": "regenerate",
                        "reason": "merged_bodies",
                        "severity": issue.get("severity", "high"),
                        "action": "increase_person_spacing",
                    }
                )

        return fixes

    def get_validation_summary(self, result: AnatomyValidationResult) -> str:
        """Get human-readable validation summary."""
        lines: List[str] = []
        lines.append(f"Validation: {'PASS' if result.is_valid else 'FAIL'}")
        lines.append(f"Overall Score: {result.overall_score:.2f}")
        lines.append(f"Issues: {len(result.issues)}")

        if result.issues:
            lines.append("\nIssues Found:")
            for issue in result.issues:
                msg = issue.get("message", str(issue))
                sev = issue.get("severity", "unknown").upper()
                lines.append(f"  - [{sev}] {msg}")

        lines.append("\nModel Results:")
        lines.append(f"  YOLO: {result.scores.get('person_count_yolo', 0):.2f}")
        lines.append(f"  Faces: {result.scores.get('faces', 0):.2f}")
        lines.append(f"  Hands: {result.scores.get('hands', 0):.2f}")
        lines.append(f"  Segmentation: {result.scores.get('body_separation', 0):.2f}")

        return "\n".join(lines)
