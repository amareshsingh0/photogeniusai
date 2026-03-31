"""
Tests for Camera Intelligence & Occlusion Solver.
P0: Zero head occlusions in layout phase.

Run from ai-pipeline root:
  python -m pytest tests/test_camera_occlusion_solver.py -v -p no:asyncio
"""

import pytest

try:
    from services.camera_occlusion_solver import (
        CameraOcclusionSolver,
        CameraConfig,
        OcclusionSafeLayout,
        HEAD_CLEARANCE,
    )
except ImportError:
    from ai_pipeline.services.camera_occlusion_solver import (
        CameraOcclusionSolver,
        CameraConfig,
        OcclusionSafeLayout,
        HEAD_CLEARANCE,
    )

try:
    from services.scene_graph_compiler import SceneGraphCompiler
except ImportError:
    from ai_pipeline.services.scene_graph_compiler import SceneGraphCompiler


def _solver():
    return CameraOcclusionSolver(canvas_width=1024, canvas_height=1024)


def test_fov_from_entity_count():
    """FOV calculation based on entity count: more entities → wider FOV."""
    solver = _solver()
    fov_1 = solver.compute_fov_for_full_visibility(1, 0)
    fov_3 = solver.compute_fov_for_full_visibility(3, 0)
    fov_5 = solver.compute_fov_for_full_visibility(5, 1)
    assert fov_1 <= fov_3 <= fov_5
    assert 45 <= fov_1 <= 90
    assert 45 <= fov_5 <= 90


def test_detect_head_occlusions_empty_when_umbrella_above():
    """Occlusion detection: zero when umbrella is above all heads."""
    solver = _solver()
    layout = {
        "entities": [
            {
                "id": "person_1",
                "type": "person",
                "head_position": (200, 400),
                "head_radius": 40,
                "bbox": (170, 200, 230, 500),
            },
            {
                "id": "object_umbrella_1",
                "type": "umbrella",
                "center": (200, 120),
                "radius": 150,
            },
        ]
    }
    occlusions = solver.detect_head_occlusions(layout)
    assert occlusions == [], "Umbrella above head should yield zero occlusions"


def test_detect_head_occlusions_nonzero_when_overlap():
    """Occlusion detection: non-zero when object overlaps head circle."""
    solver = _solver()
    layout = {
        "entities": [
            {
                "id": "person_1",
                "type": "person",
                "head_position": (200, 400),
                "head_radius": 50,
                "bbox": (170, 200, 230, 500),
            },
            {
                "id": "object_umbrella_1",
                "type": "umbrella",
                "center": (200, 380),
                "radius": 150,
            },
        ]
    }
    occlusions = solver.detect_head_occlusions(layout)
    assert len(occlusions) >= 1, "Umbrella overlapping head should be detected"


def test_solve_zero_head_occlusions():
    """Solve returns layout with occlusion_count=0 for compiler output."""
    compiler = SceneGraphCompiler(use_spacy=False)
    solver = _solver()
    result = compiler.compile("Mother with 2 children under umbrella in rain")
    layout = result["layout"]
    camera = result["camera"]
    safe = solver.solve(layout, camera)
    assert isinstance(safe, OcclusionSafeLayout)
    assert safe.occlusion_count == 0, "Layout phase must achieve zero head occlusions"
    assert len(safe.head_visibility_mask) == 3
    assert safe.camera.fov >= 45


def test_solve_height_tilt_present():
    """Camera config has height and tilt for full visibility."""
    compiler = SceneGraphCompiler(use_spacy=False)
    solver = _solver()
    result = compiler.compile("Couple at beach")
    safe = solver.solve(result["layout"], result["camera"])
    assert hasattr(safe.camera, "height")
    assert hasattr(safe.camera, "tilt")
    assert hasattr(safe.camera, "fov")


def test_to_prompt_hints():
    """to_prompt_hints exports person_count, head positions, camera."""
    compiler = SceneGraphCompiler(use_spacy=False)
    solver = _solver()
    result = compiler.compile("3 people in park")
    safe = solver.solve(result["layout"], result["camera"])
    hints = solver.to_prompt_hints(safe)
    assert hints["person_count"] == 3
    assert "head_positions_normalized" in hints
    assert "camera_fov" in hints
    assert "camera_tilt" in hints


def test_camera_fov_wider_for_more_people():
    """Compiler + solver: FOV wider for family of 5 than for couple."""
    compiler = SceneGraphCompiler(use_spacy=False)
    solver = _solver()
    r_small = compiler.compile("Couple at sunset")
    r_large = compiler.compile("Family of 5 at picnic")
    safe_small = solver.solve(r_small["layout"], r_small["camera"])
    safe_large = solver.solve(r_large["layout"], r_large["camera"])
    assert safe_large.camera.fov >= safe_small.camera.fov


def test_fov_sqrt_mode_avoids_maxing_in_crowds():
    """FOV with sqrt scale mode grows gently for many entities (no early cap at 90)."""
    solver_linear = CameraOcclusionSolver(
        canvas_width=1024, canvas_height=1024, fov_scale_mode="linear"
    )
    solver_sqrt = CameraOcclusionSolver(
        canvas_width=1024, canvas_height=1024, fov_scale_mode="sqrt"
    )
    fov_linear_10 = solver_linear.compute_fov_for_full_visibility(10, 0)
    fov_sqrt_10 = solver_sqrt.compute_fov_for_full_visibility(10, 0)
    # Linear: 50 + 6*9 = 104 -> capped 90. Sqrt: 50 + 6*sqrt(9) = 68
    assert fov_linear_10 == 90.0
    assert fov_sqrt_10 < 90.0
    assert 60 <= fov_sqrt_10 <= 75


def test_detect_head_occlusions_hat_above_empty():
    """Occlusion detection: zero when hat is above head."""
    solver = _solver()
    layout = {
        "entities": [
            {
                "id": "person_1",
                "type": "person",
                "head_position": (300, 350),
                "head_radius": 40,
                "bbox": (260, 180, 340, 520),
            },
            {
                "id": "object_hat_1",
                "type": "hat",
                "center": (300, 260),
                "radius": 45,
            },
        ]
    }
    occlusions = solver.detect_head_occlusions(layout)
    assert occlusions == [], "Hat above head should yield zero occlusions"


def test_detect_head_occlusions_hat_overlap():
    """Occlusion detection: non-zero when hat overlaps head."""
    solver = _solver()
    layout = {
        "entities": [
            {
                "id": "person_1",
                "type": "person",
                "head_position": (300, 350),
                "head_radius": 45,
                "bbox": (260, 180, 340, 520),
            },
            {
                "id": "object_hat_1",
                "type": "hat",
                "center": (300, 340),
                "radius": 45,
            },
        ]
    }
    occlusions = solver.detect_head_occlusions(layout)
    assert len(occlusions) >= 1, "Hat overlapping head should be detected"


def test_solve_zero_head_occlusions_with_hat():
    """Solve achieves zero occlusions when layout has hat (resolved above head)."""
    solver = _solver()
    layout = {
        "entities": [
            {
                "id": "person_1",
                "type": "person",
                "head_position": (200, 400),
                "head_radius": 40,
                "bbox": (170, 200, 230, 500),
            },
            {
                "id": "object_hat_1",
                "type": "hat",
                "center": (200, 380),
                "radius": 45,
            },
        ]
    }
    camera = {"fov": 55, "height": 1.6, "tilt": 0, "frame": {}}
    safe = solver.solve(layout, camera)
    assert safe.occlusion_count == 0
    hat = next((e for e in safe.entities if e.get("type") == "hat"), None)
    assert hat is not None
    # Hat center should be above head top (400 - 40 = 360); clearance 80 -> safe bottom 280
    assert (
        hat["center"][1] + hat["radius"] <= 400 - 40 - 80 + 1
    )  # allow small float tolerance


def test_solve_furniture_below_heads():
    """Solve moves furniture bbox below head band so zero head occlusions."""
    solver = _solver()
    layout = {
        "entities": [
            {
                "id": "person_1",
                "type": "person",
                "head_position": (300, 320),
                "head_radius": 40,
                "bbox": (260, 150, 340, 500),
            },
            {
                "id": "furniture_chair_1",
                "type": "furniture",
                "bbox": (200, 200, 400, 380),
            },
        ]
    }
    camera = {"fov": 55, "height": 1.6, "tilt": 0, "frame": {}}
    safe = solver.solve(layout, camera)
    assert safe.occlusion_count == 0
    chair = next((e for e in safe.entities if e.get("type") == "furniture"), None)
    assert chair is not None
    # Chair top should be below head bottom (320+40)+80 = 440
    assert chair["bbox"][1] >= 320 + 40 + 80 - 1


def test_height_eye_factor_tuning():
    """Solver uses configurable height_eye_factor for eye-level."""
    solver_default = CameraOcclusionSolver(
        canvas_width=1024, canvas_height=1024, height_eye_factor=0.35
    )
    solver_high = CameraOcclusionSolver(
        canvas_width=1024, canvas_height=1024, height_eye_factor=0.5
    )
    layout = {
        "entities": [
            {
                "id": "person_1",
                "type": "person",
                "head_position": (200, 300),
                "head_radius": 40,
                "bbox": (170, 100, 230, 500),
            },
        ]
    }
    camera = {"fov": 50, "height": 1.6, "tilt": 0, "frame": {}}
    safe_default = solver_default.solve(layout, camera)
    safe_high = solver_high.solve(layout, camera)
    # Higher factor -> eye_level_y further down in frame
    assert safe_high.camera.eye_level_y >= safe_default.camera.eye_level_y
