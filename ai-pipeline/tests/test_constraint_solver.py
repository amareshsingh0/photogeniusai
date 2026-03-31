"""
Tests for Constraint Solver.
Converts scene graph hard_constraints into prompt additions and validation rules.
"""

import pytest

try:
    from services.constraint_solver import (
        ConstraintSolver,
        SolverResult,
        _get_constraint_list,
    )
except ImportError:
    from ai_pipeline.services.constraint_solver import (
        ConstraintSolver,
        SolverResult,
        _get_constraint_list,
    )


def test_solver_result_merge_into_prompt():
    """SolverResult.merge_into_prompt appends positive_additions."""
    r = SolverResult(positive_additions=["exactly 4 people", "all heads visible"])
    out = r.merge_into_prompt("A family at the beach")
    assert "exactly 4 people" in out
    assert "all heads visible" in out
    assert "A family at the beach" in out


def test_solver_result_merge_into_negative():
    """SolverResult.merge_into_negative appends negative_additions."""
    r = SolverResult(negative_additions=["extra person", "blurry"])
    out = r.merge_into_negative("low quality")
    assert "extra person" in out
    assert "blurry" in out


def test_get_constraint_list_from_hard_constraints():
    """_get_constraint_list uses hard_constraints when present."""
    scene = {
        "hard_constraints": [
            {"type": "count", "rule": "exactly_4_people", "severity": "critical"},
            {"type": "visibility", "rule": "no_heads_occluded_by_objects", "severity": "critical"},
        ],
    }
    lst = _get_constraint_list(scene)
    assert len(lst) == 2
    assert lst[0]["rule"] == "exactly_4_people"
    assert lst[1]["rule"] == "no_heads_occluded_by_objects"


def test_solve_exactly_n_people():
    """Constraint exactly_N_people yields positive/negative additions and validation_rules."""
    solver = ConstraintSolver()
    scene = {
        "hard_constraints": [
            {"type": "count", "rule": "exactly_4_people", "severity": "critical"},
        ],
    }
    result = solver.solve(scene)
    assert result.validation_rules.get("person_count") == 4
    assert any("exactly 4 people" in p for p in result.positive_additions)
    assert any("more than 4 people" in n for n in result.negative_additions)
    assert any("less than 4 people" in n for n in result.negative_additions)


def test_solve_hands_holding_book():
    """Constraint hands_holding_book_correctly yields hand/object additions."""
    solver = ConstraintSolver()
    scene = {
        "hard_constraints": [
            {"type": "anatomy", "rule": "hands_holding_book_correctly", "severity": "high"},
        ],
    }
    result = solver.solve(scene)
    assert result.validation_rules.get("hands_holding") == "book"
    assert any("holding book" in p.lower() for p in result.positive_additions)
    assert any("extra fingers" in n or "malformed hands" in n for n in result.negative_additions)


def test_solve_clean_background_centered_subject():
    """Constraints centered_subject and clean_background yield composition_rules."""
    solver = ConstraintSolver()
    scene = {
        "hard_constraints": [
            {"type": "spatial", "rule": "centered_subject", "severity": "critical"},
            {"type": "visibility", "rule": "clean_background", "severity": "high"},
        ],
    }
    result = solver.solve(scene)
    assert result.composition_rules.get("center_subject") is True
    assert result.composition_rules.get("background_blur") == 0.8
    assert result.validation_rules.get("clean_product_background") is True
    assert any("clean background" in p.lower() for p in result.positive_additions)


def test_solve_no_merged_bodies():
    """Constraint no_merged_bodies yields separation positives and validation_rules."""
    solver = ConstraintSolver()
    scene = {
        "hard_constraints": [
            {"type": "spatial", "rule": "no_merged_bodies", "severity": "critical"},
        ],
    }
    result = solver.solve(scene)
    assert result.validation_rules.get("no_merged_bodies") is True
    assert any("separation" in p.lower() for p in result.positive_additions)


def test_solve_exactly_heads_visible():
    """Rule exactly_N_heads_fully_visible sets validation and additions."""
    solver = ConstraintSolver()
    scene = {
        "hard_constraints": [
            {"type": "visibility", "rule": "exactly_3_heads_fully_visible", "severity": "critical"},
        ],
    }
    result = solver.solve(scene)
    assert result.validation_rules.get("person_count") == 3
    assert any("3 heads" in p or "all 3 heads" in p for p in result.positive_additions)


def test_solve_dedup_additions():
    """Solver deduplicates positive and negative additions (case-insensitive)."""
    solver = ConstraintSolver()
    scene = {
        "hard_constraints": [
            {"type": "count", "rule": "exactly_2_people", "severity": "critical"},
            {"type": "visibility", "rule": "exactly_2_heads_fully_visible", "severity": "critical"},
        ],
    }
    result = solver.solve(scene)
    assert len(result.positive_additions) >= 1
    assert len(result.negative_additions) >= 1
    # No duplicate entries (solver deduplicates by lowercased string)
    assert len(result.positive_additions) == len(set(p.lower() for p in result.positive_additions))
    assert len(result.negative_additions) == len(set(n.lower() for n in result.negative_additions))


def test_solve_empty_scene():
    """Empty or missing constraints returns empty SolverResult."""
    solver = ConstraintSolver()
    result = solver.solve({})
    assert result.positive_additions == []
    assert result.negative_additions == []
    assert result.validation_rules == {}
    assert result.composition_rules == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:asyncio"])
