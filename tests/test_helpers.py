"""
Unit tests for helper utilities — no PySpark required.
"""

from lakehouse.utils.helpers import safe_divide, format_percentage


class TestSafeDivide:
    def test_normal_division(self):
        assert safe_divide(10, 2) == 5.0

    def test_zero_division_returns_default(self):
        assert safe_divide(10, 0) == 0

    def test_zero_division_custom_default(self):
        assert safe_divide(10, 0, default=-1) == -1

    def test_float_division(self):
        assert safe_divide(1, 3) == pytest.approx(0.333, rel=1e-2)


class TestFormatPercentage:
    def test_basic_percentage(self):
        assert format_percentage(0.5) == 50.0

    def test_custom_decimals(self):
        assert format_percentage(0.12345, decimals=1) == 12.3

    def test_zero(self):
        assert format_percentage(0) == 0.0

    def test_one(self):
        assert format_percentage(1.0) == 100.0


import pytest  # noqa: E402
