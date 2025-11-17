#!/usr/bin/env bash
#
# Seed test data into Cassandra for CDC pipeline testing
# Inserts 1000 users and 5000 orders to test throughput and lag
#

set -euo pipefail

# Configuration
CASSANDRA_HOST="${CASSANDRA_HOST:-localhost}"
CASSANDRA_PORT="${CASSANDRA_PORT:-9042}"
KEYSPACE="ecommerce"
NUM_USERS="${NUM_USERS:-1000}"
NUM_ORDERS="${NUM_ORDERS:-5000}"

echo "=== CDC Test Data Seeder ==="
echo "Cassandra: $CASSANDRA_HOST:$CASSANDRA_PORT"
echo "Keyspace: $KEYSPACE"
echo "Users to create: $NUM_USERS"
echo "Orders to create: $NUM_ORDERS"
echo ""

# Check if cqlsh is available
if ! command -v cqlsh &> /dev/null; then
    echo "ERROR: cqlsh not found. Please install cassandra-driver:"
    echo "  pip install cassandra-driver"
    exit 1
fi

# Wait for Cassandra to be ready
echo "Waiting for Cassandra to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if cqlsh "$CASSANDRA_HOST" "$CASSANDRA_PORT" -e "DESCRIBE KEYSPACES" &> /dev/null; then
        echo "✓ Cassandra is ready"
        break
    fi
    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts: Cassandra not ready yet..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Cassandra did not become ready in time"
    exit 1
fi

# Create keyspace if not exists
echo "Creating keyspace if not exists..."
cqlsh "$CASSANDRA_HOST" "$CASSANDRA_PORT" <<EOF
CREATE KEYSPACE IF NOT EXISTS $KEYSPACE
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};
EOF
echo "✓ Keyspace ready"

# Create users table
echo "Creating users table..."
cqlsh "$CASSANDRA_HOST" "$CASSANDRA_PORT" <<EOF
CREATE TABLE IF NOT EXISTS $KEYSPACE.users (
    user_id uuid PRIMARY KEY,
    email text,
    name text,
    created_at timestamp,
    last_login timestamp,
    is_active boolean
);
EOF
echo "✓ Users table ready"

# Create orders table
echo "Creating orders table..."
cqlsh "$CASSANDRA_HOST" "$CASSANDRA_PORT" <<EOF
CREATE TABLE IF NOT EXISTS $KEYSPACE.orders (
    order_id uuid PRIMARY KEY,
    user_id uuid,
    total decimal,
    status text,
    created_at timestamp,
    updated_at timestamp
);
EOF
echo "✓ Orders table ready"

# Generate and insert user data using Python
echo "Inserting $NUM_USERS users..."
python3 << PYTHON_SCRIPT
from cassandra.cluster import Cluster
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import random

cluster = Cluster(['$CASSANDRA_HOST'], port=$CASSANDRA_PORT)
session = cluster.connect('$KEYSPACE')

# Prepare insert statement
insert_user = session.prepare("""
    INSERT INTO users (user_id, email, name, created_at, last_login, is_active)
    VALUES (?, ?, ?, ?, ?, ?)
""")

print("Generating $NUM_USERS users...")
batch_size = 100
for i in range($NUM_USERS):
    user_id = uuid4()
    email = f"user{i}@example.com"
    name = f"User {i}"
    created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 365))
    last_login = datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 720))
    is_active = random.choice([True, False])

    session.execute(insert_user, (user_id, email, name, created_at, last_login, is_active))

    if (i + 1) % batch_size == 0:
        print(f"  Inserted {i + 1}/$NUM_USERS users...")

print(f"✓ Inserted all $NUM_USERS users")

# Keep some user IDs for orders
user_ids_query = session.execute("SELECT user_id FROM users LIMIT $NUM_USERS")
user_ids = [row.user_id for row in user_ids_query]

# Prepare order insert
insert_order = session.prepare("""
    INSERT INTO orders (order_id, user_id, total, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
""")

print("Generating $NUM_ORDERS orders...")
statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']

for i in range($NUM_ORDERS):
    order_id = uuid4()
    user_id = random.choice(user_ids)
    total = round(random.uniform(10.0, 500.0), 2)
    status = random.choice(statuses)
    created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 90))
    updated_at = created_at + timedelta(hours=random.randint(0, 48))

    session.execute(insert_order, (order_id, user_id, total, status, created_at, updated_at))

    if (i + 1) % batch_size == 0:
        print(f"  Inserted {i + 1}/$NUM_ORDERS orders...")

print(f"✓ Inserted all $NUM_ORDERS orders")

session.shutdown()
cluster.shutdown()
PYTHON_SCRIPT

echo ""
echo "=== Data Seeding Complete ==="
echo "Users: $NUM_USERS"
echo "Orders: $NUM_ORDERS"
echo ""
echo "Verify with:"
echo "  cqlsh $CASSANDRA_HOST $CASSANDRA_PORT -e \"SELECT COUNT(*) FROM $KEYSPACE.users;\""
echo "  cqlsh $CASSANDRA_HOST $CASSANDRA_PORT -e \"SELECT COUNT(*) FROM $KEYSPACE.orders;\""
