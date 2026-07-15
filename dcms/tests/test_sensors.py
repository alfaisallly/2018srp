import pytest

from app.models import SensorStatus
from app.services.sensor_engine import (
    DEFAULT_SENSOR_TEMPLATES,
    evaluate_sensor_value,
    SENSOR_STATUS_COLORS,
)


def test_evaluate_sensor_up():
    status, msg = evaluate_sensor_value(50, warning_limit=80, error_limit=90)
    assert status == SensorStatus.UP


def test_evaluate_sensor_warning():
    status, _ = evaluate_sensor_value(85, warning_limit=80, error_limit=90)
    assert status == SensorStatus.WARNING


def test_evaluate_sensor_down():
    status, _ = evaluate_sensor_value(95, warning_limit=80, error_limit=90)
    assert status == SensorStatus.DOWN


def test_evaluate_reachable_down():
    status, _ = evaluate_sensor_value(0, warning_limit=None, error_limit=0.5, higher_is_worse=False)
    assert status == SensorStatus.DOWN


def test_evaluate_paused():
    status, _ = evaluate_sensor_value(50, warning_limit=80, error_limit=90, enabled=False)
    assert status == SensorStatus.PAUSED


def test_status_colors_defined():
    for status in SensorStatus:
        assert status in SENSOR_STATUS_COLORS


def test_default_templates_have_cpu():
    assert "cpu_utilization" in DEFAULT_SENSOR_TEMPLATES
    assert DEFAULT_SENSOR_TEMPLATES["cpu_utilization"].warning == 80
