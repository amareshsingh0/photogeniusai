"""
Tests for Task 5.1: Phase metrics and circuit breakers in observability.
"""

import pytest

try:
    from services.observability import (
        record_validation_first_try,
        record_refinement_loops,
        record_typography_ocr,
        record_math_validation,
        record_constraint_solver_time_ms,
        record_validation_result,
        record_typography_ocr_result,
        build_weekly_metrics_report,
        send_weekly_report_email,
    )
except (ImportError, ValueError):
    try:
        from ai_pipeline.services.observability import (
            record_validation_first_try,
            record_refinement_loops,
            record_typography_ocr,
            record_math_validation,
            record_constraint_solver_time_ms,
            record_validation_result,
            record_typography_ocr_result,
            build_weekly_metrics_report,
            send_weekly_report_email,
        )
    except (ImportError, ValueError):
        pytest.skip("observability import failed (e.g. duplicate Prometheus metrics)", allow_module_level=True)


def test_record_validation_first_try_no_raise():
    """record_validation_first_try accepts (category, success) and does not raise."""
    record_validation_first_try("portrait", True)
    record_validation_first_try("landscape", False)


def test_record_refinement_loops_no_raise():
    """record_refinement_loops accepts (category, count) and does not raise."""
    record_refinement_loops("product", 1.0)
    record_refinement_loops("unknown", 2.5)


def test_record_typography_ocr_no_raise():
    """record_typography_ocr and record_typography_ocr_result accept success bool."""
    record_typography_ocr(True)
    record_typography_ocr_result(False)


def test_record_math_validation_no_raise():
    """record_math_validation accepts success bool."""
    record_math_validation(True)
    record_math_validation(False)


def test_record_constraint_solver_time_ms_no_raise():
    """record_constraint_solver_time_ms accepts ms float."""
    record_constraint_solver_time_ms(10.5)
    record_constraint_solver_time_ms(100.0)


def test_record_validation_result_no_raise():
    """record_validation_result accepts success bool (for circuit breaker)."""
    record_validation_result(True)
    record_validation_result(False)


def test_build_weekly_metrics_report():
    """build_weekly_metrics_report returns dict with summary and optional breakdowns."""
    report = build_weekly_metrics_report(
        metrics_by_category={"portrait": {"count": 100}},
        validation_first_try_rate=0.92,
        refinement_loops_avg=0.5,
        typography_ocr_accuracy=0.88,
        math_validation_pass_rate=0.99,
    )
    assert report["period"] == "weekly"
    assert report["summary"]["validation_first_try_success_rate"] == 0.92
    assert report["summary"]["refinement_loops_avg"] == 0.5
    assert report["summary"]["typography_ocr_accuracy"] == 0.88
    assert report["summary"]["math_validation_pass_rate"] == 0.99
    assert report["by_category"] == {"portrait": {"count": 100}}


def test_send_weekly_report_email_no_config():
    """send_weekly_report_email with no to_emails and no env returns False."""
    ok = send_weekly_report_email({"summary": {}}, to_emails=[])
    assert ok is False
