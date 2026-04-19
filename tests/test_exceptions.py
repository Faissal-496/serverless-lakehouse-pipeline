"""
Unit tests for custom exceptions — no PySpark required.
"""

from lakehouse.core.exceptions import (
    LakehouseException,
    ConfigurationError,
    DataSourceError,
    PersistenceError,
)


class TestExceptions:
    def test_lakehouse_exception_is_base(self):
        with pytest.raises(LakehouseException):
            raise LakehouseException("base error")

    def test_configuration_error_inherits(self):
        err = ConfigurationError("bad config")
        assert isinstance(err, LakehouseException)
        assert "bad config" in str(err)

    def test_data_source_error_inherits(self):
        err = DataSourceError("bad source")
        assert isinstance(err, LakehouseException)

    def test_persistence_error_inherits(self):
        err = PersistenceError("write failed")
        assert isinstance(err, LakehouseException)


import pytest  # noqa: E402
