"""
Unit tests for schema mapper
Tests Cassandra → warehouse type mapping logic
"""

import pytest
from uuid import UUID
from datetime import datetime

from src.transform.schema_mapper import (
    SchemaMapper,
    map_cassandra_to_postgres,
    map_cassandra_to_clickhouse,
    map_cassandra_to_timescaledb,
)


class TestSchemaMapper:
    """Test Cassandra type mapping to warehouse types"""

    def test_uuid_mapping_to_postgres(self):
        """Test UUID mapping to Postgres"""
        cassandra_type = "UUID"
        postgres_type = map_cassandra_to_postgres(cassandra_type)

        assert postgres_type == "uuid"

    def test_uuid_mapping_to_clickhouse(self):
        """Test UUID mapping to ClickHouse"""
        cassandra_type = "UUID"
        clickhouse_type = map_cassandra_to_clickhouse(cassandra_type)

        assert clickhouse_type == "UUID"

    def test_text_mapping_to_postgres(self):
        """Test TEXT mapping to Postgres"""
        assert map_cassandra_to_postgres("TEXT") == "text"
        assert map_cassandra_to_postgres("VARCHAR") == "varchar"

    def test_text_mapping_to_clickhouse(self):
        """Test TEXT mapping to ClickHouse"""
        assert map_cassandra_to_clickhouse("TEXT") == "String"
        assert map_cassandra_to_clickhouse("VARCHAR") == "String"

    def test_timestamp_mapping_to_postgres(self):
        """Test TIMESTAMP mapping to Postgres"""
        assert map_cassandra_to_postgres("TIMESTAMP") == "timestamptz"

    def test_timestamp_mapping_to_clickhouse(self):
        """Test TIMESTAMP mapping to ClickHouse"""
        assert map_cassandra_to_clickhouse("TIMESTAMP") == "DateTime64(3)"

    def test_map_to_json_for_complex_types(self):
        """Test that complex types (MAP, LIST, SET) map to JSON/JSONB"""
        # Postgres uses JSONB
        assert map_cassandra_to_postgres("MAP") == "jsonb"
        assert map_cassandra_to_postgres("LIST") == "jsonb"
        assert map_cassandra_to_postgres("SET") == "jsonb"

        # ClickHouse uses String (will serialize to JSON)
        assert map_cassandra_to_clickhouse("MAP") == "String"
        assert map_cassandra_to_clickhouse("LIST") == "String"

    def test_timescaledb_inherits_from_postgres(self):
        """Test that TimescaleDB mappings inherit from Postgres"""
        assert map_cassandra_to_timescaledb("UUID") == "uuid"
        assert map_cassandra_to_timescaledb("TEXT") == "text"

    def test_schema_mapper_load_from_yaml(self):
        """Test SchemaMapper loads mappings from YAML config"""
        mapper = SchemaMapper()
        mapper.load_mappings()

        assert mapper.postgres_mappings is not None
        assert mapper.clickhouse_mappings is not None
        assert mapper.timescaledb_mappings is not None

    def test_convert_uuid_value(self):
        """Test converting UUID values"""
        from src.transform.schema_mapper import convert_value

        uuid_str = "550e8400-e29b-41d4-a716-446655440000"

        # Should remain as string for all warehouses
        assert convert_value(uuid_str, "UUID", "postgres") == uuid_str

    def test_convert_timestamp_value(self):
        """Test converting timestamp values"""
        from src.transform.schema_mapper import convert_value

        # Cassandra timestamp is microseconds since epoch
        timestamp_micros = 1700000000000000

        # Should convert to appropriate format for each warehouse
        result = convert_value(timestamp_micros, "TIMESTAMP", "postgres")
        assert result is not None
