"""
Unit tests for schema change detection
Tests schema comparison and change detection logic
"""

import pytest
from typing import Dict, Any


class TestSchemaDetection:
    """Test schema change detection logic"""

    def test_detect_add_column(self):
        """Test detection of ADD COLUMN schema change"""
        from src.models.schema import TableSchema, SchemaChange, SchemaChangeType

        # Old schema: users table with id, email
        old_schema = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        # New schema: added 'created_at' column
        new_schema = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
                "created_at": "timestamp",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        # Detect changes
        changes = old_schema.compare(new_schema)

        assert len(changes) == 1
        assert changes[0].change_type == SchemaChangeType.ADD_COLUMN
        assert changes[0].column_name == "created_at"
        assert changes[0].new_type == "timestamp"

    def test_detect_drop_column(self):
        """Test detection of DROP COLUMN schema change"""
        from src.models.schema import TableSchema, SchemaChangeType

        old_schema = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
                "phone": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        # New schema: dropped 'phone' column
        new_schema = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        changes = old_schema.compare(new_schema)

        assert len(changes) == 1
        assert changes[0].change_type == SchemaChangeType.DROP_COLUMN
        assert changes[0].column_name == "phone"

    def test_detect_alter_type(self):
        """Test detection of ALTER TYPE schema change"""
        from src.models.schema import TableSchema, SchemaChangeType

        old_schema = TableSchema(
            keyspace="ecommerce",
            table_name="orders",
            columns={
                "order_id": "uuid",
                "total": "decimal",
            },
            partition_keys=["order_id"],
            clustering_keys=[],
        )

        # New schema: changed 'total' from decimal to double
        new_schema = TableSchema(
            keyspace="ecommerce",
            table_name="orders",
            columns={
                "order_id": "uuid",
                "total": "double",
            },
            partition_keys=["order_id"],
            clustering_keys=[],
        )

        changes = old_schema.compare(new_schema)

        assert len(changes) == 1
        assert changes[0].change_type == SchemaChangeType.ALTER_TYPE
        assert changes[0].column_name == "total"
        assert changes[0].old_type == "decimal"
        assert changes[0].new_type == "double"

    def test_detect_multiple_changes(self):
        """Test detection of multiple schema changes at once"""
        from src.models.schema import TableSchema, SchemaChangeType

        old_schema = TableSchema(
            keyspace="ecommerce",
            table_name="products",
            columns={
                "product_id": "uuid",
                "name": "text",
                "price": "decimal",
                "old_field": "text",
            },
            partition_keys=["product_id"],
            clustering_keys=[],
        )

        new_schema = TableSchema(
            keyspace="ecommerce",
            table_name="products",
            columns={
                "product_id": "uuid",
                "name": "text",
                "price": "double",  # Type changed
                "category": "text",  # Added
            },
            partition_keys=["product_id"],
            clustering_keys=[],
        )

        changes = old_schema.compare(new_schema)

        # Should detect: DROP old_field, ALTER price type, ADD category
        assert len(changes) == 3

        change_types = {change.change_type for change in changes}
        assert SchemaChangeType.ADD_COLUMN in change_types
        assert SchemaChangeType.DROP_COLUMN in change_types
        assert SchemaChangeType.ALTER_TYPE in change_types

    def test_no_changes_detected(self):
        """Test that identical schemas produce no changes"""
        from src.models.schema import TableSchema

        schema1 = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        schema2 = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        changes = schema1.compare(schema2)

        assert len(changes) == 0

    def test_schema_version_tracking(self):
        """Test that schema versions are tracked correctly"""
        from src.models.schema import TableSchema

        schema = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
            version=1,
        )

        assert schema.version == 1

        # After schema change, version should increment
        updated_schema = schema.with_version(2)
        assert updated_schema.version == 2

    def test_schema_hash_calculation(self):
        """Test that schema hash is calculated consistently"""
        from src.models.schema import TableSchema

        schema1 = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        schema2 = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        # Identical schemas should have same hash
        assert schema1.get_hash() == schema2.get_hash()

        # Different schemas should have different hash
        schema3 = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
                "created_at": "timestamp",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        assert schema1.get_hash() != schema3.get_hash()

    def test_is_compatible_change(self):
        """Test detection of compatible vs incompatible schema changes"""
        from src.models.schema import SchemaChange, SchemaChangeType

        # ADD COLUMN is compatible
        add_change = SchemaChange(
            change_type=SchemaChangeType.ADD_COLUMN,
            column_name="new_field",
            new_type="text",
        )
        assert add_change.is_compatible()

        # DROP COLUMN is compatible
        drop_change = SchemaChange(
            change_type=SchemaChangeType.DROP_COLUMN,
            column_name="old_field",
        )
        assert drop_change.is_compatible()

        # Some ALTER TYPE changes are incompatible (e.g., text -> int)
        incompatible_alter = SchemaChange(
            change_type=SchemaChangeType.ALTER_TYPE,
            column_name="field",
            old_type="text",
            new_type="int",
        )
        assert not incompatible_alter.is_compatible()

        # Compatible type changes (e.g., int -> bigint, decimal -> double)
        compatible_alter = SchemaChange(
            change_type=SchemaChangeType.ALTER_TYPE,
            column_name="counter",
            old_type="int",
            new_type="bigint",
        )
        assert compatible_alter.is_compatible()

    def test_schema_change_to_dict(self):
        """Test serialization of SchemaChange to dictionary"""
        from src.models.schema import SchemaChange, SchemaChangeType

        change = SchemaChange(
            change_type=SchemaChangeType.ADD_COLUMN,
            column_name="created_at",
            new_type="timestamp",
        )

        change_dict = change.to_dict()

        assert change_dict["change_type"] == "ADD_COLUMN"
        assert change_dict["column_name"] == "created_at"
        assert change_dict["new_type"] == "timestamp"

    def test_partition_key_change_detection(self):
        """Test that partition key changes are detected as incompatible"""
        from src.models.schema import TableSchema

        old_schema = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["user_id"],
            clustering_keys=[],
        )

        # Changing partition key is incompatible
        new_schema = TableSchema(
            keyspace="ecommerce",
            table_name="users",
            columns={
                "user_id": "uuid",
                "email": "text",
            },
            partition_keys=["email"],  # Changed partition key
            clustering_keys=[],
        )

        changes = old_schema.compare(new_schema)

        # Should detect partition key change as incompatible
        has_incompatible = any(not change.is_compatible() for change in changes)
        assert has_incompatible

    def test_clustering_key_change_detection(self):
        """Test that clustering key changes are detected"""
        from src.models.schema import TableSchema

        old_schema = TableSchema(
            keyspace="ecommerce",
            table_name="orders",
            columns={
                "user_id": "uuid",
                "order_id": "uuid",
                "created_at": "timestamp",
            },
            partition_keys=["user_id"],
            clustering_keys=["created_at"],
        )

        # Changing clustering key
        new_schema = TableSchema(
            keyspace="ecommerce",
            table_name="orders",
            columns={
                "user_id": "uuid",
                "order_id": "uuid",
                "created_at": "timestamp",
            },
            partition_keys=["user_id"],
            clustering_keys=["order_id"],  # Changed clustering key
        )

        changes = old_schema.compare(new_schema)

        # Should detect clustering key change
        assert len(changes) > 0
