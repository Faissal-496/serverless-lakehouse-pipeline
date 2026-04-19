"""
Unit tests for schema registry — requires PySpark for StructType.
"""

import pytest

pyspark = pytest.importorskip("pyspark")


class TestSchemaRegistry:
    """Validate schema definitions are importable and well-formed."""

    def test_contrat2_schema_exists(self):
        from lakehouse.ingestion.schema_registry import CONTRAT2_SCHEMA
        from pyspark.sql.types import StructType

        assert isinstance(CONTRAT2_SCHEMA, StructType)
        assert len(CONTRAT2_SCHEMA.fields) > 0

    def test_client_schema_exists(self):
        from lakehouse.ingestion.schema_registry import CLIENT_SCHEMA
        from pyspark.sql.types import StructType

        assert isinstance(CLIENT_SCHEMA, StructType)
        assert len(CLIENT_SCHEMA.fields) > 0

    def test_contrat2_schema_has_key_columns(self):
        from lakehouse.ingestion.schema_registry import CONTRAT2_SCHEMA

        field_names = [f.name for f in CONTRAT2_SCHEMA.fields]
        assert "nusoc" in field_names, "Missing nusoc column"
        assert "nucon" in field_names, "Missing nucon column"

    def test_client_schema_has_key_columns(self):
        from lakehouse.ingestion.schema_registry import CLIENT_SCHEMA

        field_names = [f.name for f in CLIENT_SCHEMA.fields]
        assert "nusoc" in field_names, "Missing nusoc column"
