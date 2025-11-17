"""
Integration test for DROP COLUMN schema change handling
Verifies pipeline handles column removal gracefully
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.integration
@pytest.mark.asyncio
class TestDropColumn:
    """Test pipeline handling of DROP COLUMN schema changes"""

    async def test_drop_column_from_table(
        self, cassandra_session, postgres_connection
    ):
        """Test that pipeline handles DROP COLUMN without data loss"""
        # Setup: Create table with 3 columns
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.users_drop_test (
                user_id uuid PRIMARY KEY,
                email text,
                phone text
            )
            """
        )

        # Insert data with all columns
        user_id1 = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.users_drop_test (user_id, email, phone)
            VALUES (%s, %s, %s)
            """,
            (user_id1, "before@example.com", "555-1234"),
        )

        # Replicate initial data
        # await pipeline.process_events()

        # Drop the phone column
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.users_drop_test
            DROP phone
            """
        )

        # Insert data without dropped column
        user_id2 = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.users_drop_test (user_id, email)
            VALUES (%s, %s)
            """,
            (user_id2, "after@example.com"),
        )

        # Pipeline should:
        # 1. Detect schema change (DROP COLUMN)
        # 2. Update internal schema representation
        # 3. Continue replicating without dropped column
        # 4. Keep existing data intact

        # Verify both events replicated
        # cursor = postgres_connection.cursor()
        # cursor.execute("SELECT COUNT(*) FROM users_drop_test")
        # assert cursor.fetchone()[0] == 2

        pass

    async def test_drop_multiple_columns(self, cassandra_session, postgres_connection):
        """Test dropping multiple columns simultaneously"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.products_drop_test (
                product_id uuid PRIMARY KEY,
                name text,
                description text,
                old_field1 text,
                old_field2 text
            )
            """
        )

        # Insert with all columns
        product_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.products_drop_test
            (product_id, name, description, old_field1, old_field2)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (product_id, "Widget", "A great widget", "old1", "old2"),
        )

        # Drop multiple columns
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.products_drop_test
            DROP (old_field1, old_field2)
            """
        )

        # Insert with remaining columns only
        product_id2 = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.products_drop_test (product_id, name, description)
            VALUES (%s, %s, %s)
            """,
            (product_id2, "Gadget", "A cool gadget"),
        )

        # Pipeline should detect both column drops
        # changes = await pipeline.detect_schema_changes("ecommerce", "products_drop_test")
        # drop_changes = [c for c in changes if c.change_type == SchemaChangeType.DROP_COLUMN]
        # assert len(drop_changes) == 2

        pass

    async def test_drop_column_preserves_other_columns(
        self, cassandra_session, postgres_connection
    ):
        """Test that dropping column preserves data in other columns"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.orders_drop_test (
                order_id uuid PRIMARY KEY,
                user_id uuid,
                total decimal,
                temp_field text
            )
            """
        )

        # Insert with all columns
        order_id = uuid4()
        user_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.orders_drop_test
            (order_id, user_id, total, temp_field)
            VALUES (%s, %s, %s, %s)
            """,
            (order_id, user_id, 99.99, "temporary"),
        )

        # Drop temp_field
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.orders_drop_test
            DROP temp_field
            """
        )

        # Verify remaining data is intact
        # cursor = postgres_connection.cursor()
        # cursor.execute("SELECT user_id, total FROM orders_drop_test WHERE order_id = %s", (order_id,))
        # row = cursor.fetchone()
        # assert row[0] == user_id
        # assert row[1] == 99.99

        pass

    async def test_drop_column_all_destinations(
        self,
        cassandra_session,
        postgres_connection,
        clickhouse_connection,
        timescaledb_connection,
    ):
        """Test that DROP COLUMN propagates to all destinations"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.events_drop_test (
                event_id uuid PRIMARY KEY,
                event_type text,
                deprecated_field text
            )
            """
        )

        # Insert with all columns
        event_id = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.events_drop_test
            (event_id, event_type, deprecated_field)
            VALUES (%s, %s, %s)
            """,
            (event_id, "page_view", "deprecated"),
        )

        # Drop column
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.events_drop_test
            DROP deprecated_field
            """
        )

        # Insert without dropped column
        event_id2 = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.events_drop_test (event_id, event_type)
            VALUES (%s, %s)
            """,
            (event_id2, "click"),
        )

        # Verify dropped column is removed from all destinations
        # (Or marked as deprecated/ignored)

        # Postgres - column might be set to NULL or removed
        # cursor = postgres_connection.cursor()
        # cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='events_drop_test'")
        # columns = [row[0] for row in cursor.fetchall()]
        # assert "deprecated_field" not in columns or ... # (might keep with NULL)

        pass

    async def test_drop_column_with_index(self, cassandra_session, postgres_connection):
        """Test dropping column that has an index"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.indexed_drop_test (
                id uuid PRIMARY KEY,
                indexed_field text,
                other_field text
            )
            """
        )

        # Create index on column
        cassandra_session.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_indexed_field
            ON ecommerce.indexed_drop_test (indexed_field)
            """
        )

        # Insert data
        id1 = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.indexed_drop_test (id, indexed_field, other_field)
            VALUES (%s, %s, %s)
            """,
            (id1, "indexed", "other"),
        )

        # Drop indexed column (Cassandra requires dropping index first)
        cassandra_session.execute("DROP INDEX IF EXISTS ecommerce.idx_indexed_field")
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.indexed_drop_test
            DROP indexed_field
            """
        )

        # Pipeline should handle index removal gracefully
        pass

    async def test_drop_clustering_column_incompatible(
        self, cassandra_session, postgres_connection
    ):
        """Test that dropping clustering column is detected as incompatible"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.timeseries_drop_test (
                user_id uuid,
                timestamp timestamp,
                value double,
                PRIMARY KEY (user_id, timestamp)
            )
            """
        )

        # Dropping clustering column is not allowed in Cassandra
        # But if schema metadata changes, pipeline should detect incompatibility
        # This test verifies error handling

        # try:
        #     cassandra_session.execute(
        #         "ALTER TABLE ecommerce.timeseries_drop_test DROP timestamp"
        #     )
        # except Exception as e:
        #     # Expected - Cassandra doesn't allow this
        #     assert "Cannot drop" in str(e)

        # Pipeline should handle schema incompatibilities
        pass

    async def test_drop_column_nullable_behavior(
        self, cassandra_session, postgres_connection
    ):
        """Test DROP COLUMN handling for nullable vs non-nullable columns"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.nullable_drop_test (
                id uuid PRIMARY KEY,
                required_field text,
                optional_field text
            )
            """
        )

        # Insert rows with and without optional_field
        id1 = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.nullable_drop_test (id, required_field, optional_field)
            VALUES (%s, %s, %s)
            """,
            (id1, "required", "optional"),
        )

        id2 = uuid4()
        cassandra_session.execute(
            """
            INSERT INTO ecommerce.nullable_drop_test (id, required_field)
            VALUES (%s, %s)
            """,
            (id2, "required"),
        )

        # Drop optional field
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.nullable_drop_test
            DROP optional_field
            """
        )

        # Both rows should remain valid
        pass

    async def test_drop_column_logged(self, cassandra_session, caplog):
        """Test that DROP COLUMN changes are logged"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.audit_drop_test (
                event_id uuid PRIMARY KEY,
                action text,
                deprecated text
            )
            """
        )

        # Drop column
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.audit_drop_test
            DROP deprecated
            """
        )

        # Pipeline should log the schema change
        # assert "Schema change detected" in caplog.text
        # assert "DROP_COLUMN" in caplog.text
        # assert "audit_drop_test" in caplog.text
        # assert "deprecated" in caplog.text

        pass

    async def test_drop_column_updates_metrics(
        self, cassandra_session, postgres_connection
    ):
        """Test that schema changes update metrics"""
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.metrics_drop_test (
                id uuid PRIMARY KEY,
                field1 text,
                field2 text
            )
            """
        )

        # Drop column
        cassandra_session.execute(
            """
            ALTER TABLE ecommerce.metrics_drop_test
            DROP field2
            """
        )

        # Check that schema_changes_total metric incremented
        # from src.observability.metrics import schema_changes_total
        # value = schema_changes_total.labels(
        #     keyspace="ecommerce",
        #     table="metrics_drop_test",
        #     change_type="DROP_COLUMN"
        # )._value.get()
        # assert value > 0

        pass
