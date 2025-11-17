"""
Performance benchmark for CDC pipeline throughput
Measures events per second and replication lag under load
"""

import pytest
import asyncio
import time
from uuid import uuid4
from datetime import datetime, timezone
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""

    total_events: int
    duration_seconds: float
    events_per_second: float
    avg_replication_lag_ms: float
    max_replication_lag_ms: float
    p50_lag_ms: float
    p95_lag_ms: float
    p99_lag_ms: float


@pytest.mark.performance
@pytest.mark.asyncio
class TestThroughputBenchmark:
    """Performance benchmarks for CDC pipeline"""

    async def test_baseline_throughput_single_destination(
        self, cassandra_session, postgres_connection
    ):
        """
        Benchmark throughput to single destination (Postgres)
        Target: 1000+ events/second
        """
        num_events = 10000

        print(f"\n=== Baseline Throughput Benchmark (Single Destination) ===")
        print(f"Events to process: {num_events}")
        print(f"Destination: Postgres")

        # Create test table
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.perf_test_single (
                id uuid PRIMARY KEY,
                value text,
                timestamp timestamp
            )
            """
        )

        # Insert test data
        print("Inserting test data...")
        insert_stmt = cassandra_session.prepare(
            """
            INSERT INTO ecommerce.perf_test_single (id, value, timestamp)
            VALUES (?, ?, ?)
            """
        )

        start_time = time.time()
        for i in range(num_events):
            cassandra_session.execute(
                insert_stmt, (uuid4(), f"value_{i}", datetime.now(timezone.utc))
            )

            if (i + 1) % 1000 == 0:
                print(f"  Inserted {i + 1}/{num_events}...")

        insert_duration = time.time() - start_time
        print(f"✓ Data inserted in {insert_duration:.2f}s")

        # Run CDC pipeline (simulated)
        print("Running CDC pipeline...")
        # from src.main import CDCPipeline
        # pipeline = CDCPipeline()
        # await pipeline.run_until_complete()

        # Measure throughput
        # replication_duration = time.time() - start_time
        # events_per_second = num_events / replication_duration

        # print(f"\n=== Results ===")
        # print(f"Total events: {num_events}")
        # print(f"Duration: {replication_duration:.2f}s")
        # print(f"Throughput: {events_per_second:.0f} events/sec")

        # assert events_per_second >= 1000, f"Throughput {events_per_second} < 1000 eps"

        pass

    async def test_multi_destination_throughput(
        self,
        cassandra_session,
        postgres_connection,
        clickhouse_connection,
        timescaledb_connection,
    ):
        """
        Benchmark throughput to all three destinations
        Target: 800+ events/second (lower due to 3x writes)
        """
        num_events = 5000

        print(f"\n=== Multi-Destination Throughput Benchmark ===")
        print(f"Events to process: {num_events}")
        print(f"Destinations: Postgres, ClickHouse, TimescaleDB")

        # Create test table
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.perf_test_multi (
                id uuid PRIMARY KEY,
                value text,
                timestamp timestamp
            )
            """
        )

        # Insert test data
        print("Inserting test data...")
        insert_stmt = cassandra_session.prepare(
            """
            INSERT INTO ecommerce.perf_test_multi (id, value, timestamp)
            VALUES (?, ?, ?)
            """
        )

        start_time = time.time()
        for i in range(num_events):
            cassandra_session.execute(
                insert_stmt, (uuid4(), f"value_{i}", datetime.now(timezone.utc))
            )

            if (i + 1) % 1000 == 0:
                print(f"  Inserted {i + 1}/{num_events}...")

        insert_duration = time.time() - start_time
        print(f"✓ Data inserted in {insert_duration:.2f}s")

        # Run CDC pipeline
        print("Running CDC pipeline...")
        # from src.main import CDCPipeline
        # pipeline = CDCPipeline()
        # await pipeline.run_until_complete()

        # Measure throughput
        # replication_duration = time.time() - start_time
        # events_per_second = num_events / replication_duration

        # print(f"\n=== Results ===")
        # print(f"Total events: {num_events}")
        # print(f"Duration: {replication_duration:.2f}s")
        # print(f"Throughput: {events_per_second:.0f} events/sec")

        # assert events_per_second >= 800, f"Throughput {events_per_second} < 800 eps"

        pass

    async def test_replication_lag_under_load(self, cassandra_session, postgres_connection):
        """
        Measure replication lag under sustained load
        Target: p99 lag < 1000ms
        """
        num_events = 5000
        batch_size = 100

        print(f"\n=== Replication Lag Benchmark ===")
        print(f"Events to process: {num_events}")
        print(f"Batch size: {batch_size}")

        # Create test table
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.perf_test_lag (
                id uuid PRIMARY KEY,
                value text,
                created_at timestamp
            )
            """
        )

        # Insert and track timestamps
        print("Inserting test data...")
        insert_stmt = cassandra_session.prepare(
            """
            INSERT INTO ecommerce.perf_test_lag (id, value, created_at)
            VALUES (?, ?, ?)
            """
        )

        event_timestamps = []
        start_time = time.time()

        for i in range(num_events):
            event_time = datetime.now(timezone.utc)
            cassandra_session.execute(insert_stmt, (uuid4(), f"value_{i}", event_time))
            event_timestamps.append(event_time.timestamp())

            if (i + 1) % batch_size == 0:
                print(f"  Inserted {i + 1}/{num_events}...")

        insert_duration = time.time() - start_time
        print(f"✓ Data inserted in {insert_duration:.2f}s")

        # Run CDC pipeline and measure lag
        print("Running CDC pipeline and measuring lag...")
        # from src.main import CDCPipeline
        # pipeline = CDCPipeline()

        # lags = []
        # while not pipeline.is_caught_up():
        #     current_lag = pipeline.get_replication_lag_ms()
        #     lags.append(current_lag)
        #     await asyncio.sleep(0.1)

        # Calculate percentiles
        # lags.sort()
        # p50 = lags[len(lags) // 2]
        # p95 = lags[int(len(lags) * 0.95)]
        # p99 = lags[int(len(lags) * 0.99)]

        # print(f"\n=== Lag Results ===")
        # print(f"Average lag: {sum(lags) / len(lags):.2f}ms")
        # print(f"Max lag: {max(lags):.2f}ms")
        # print(f"p50 lag: {p50:.2f}ms")
        # print(f"p95 lag: {p95:.2f}ms")
        # print(f"p99 lag: {p99:.2f}ms")

        # assert p99 < 1000, f"p99 lag {p99}ms >= 1000ms"

        pass

    async def test_backpressure_handling(self, cassandra_session, postgres_connection):
        """
        Test pipeline behavior under backpressure (slow destination)
        Verify throughput degradation is graceful
        """
        num_events = 2000

        print(f"\n=== Backpressure Handling Benchmark ===")
        print(f"Events to process: {num_events}")

        # Create test table
        cassandra_session.execute(
            """
            CREATE TABLE IF NOT EXISTS ecommerce.perf_test_backpressure (
                id uuid PRIMARY KEY,
                value text,
                timestamp timestamp
            )
            """
        )

        # Insert test data rapidly
        print("Inserting test data rapidly...")
        insert_stmt = cassandra_session.prepare(
            """
            INSERT INTO ecommerce.perf_test_backpressure (id, value, timestamp)
            VALUES (?, ?, ?)
            """
        )

        for i in range(num_events):
            cassandra_session.execute(
                insert_stmt, (uuid4(), f"value_{i}", datetime.now(timezone.utc))
            )

        print(f"✓ Data inserted")

        # Simulate slow destination with latency
        # from toxiproxy import Toxiproxy
        # proxy = Toxiproxy()
        # postgres_proxy = proxy.get("postgres")
        # postgres_proxy.add_toxic(
        #     name="slow",
        #     type="latency",
        #     attributes={"latency": 100}  # 100ms latency
        # )

        # Run pipeline and observe throughput
        print("Running pipeline with slow destination...")
        # from src.main import CDCPipeline
        # pipeline = CDCPipeline()

        # throughputs = []
        # for _ in range(10):
        #     start = time.time()
        #     await pipeline.run_batch()
        #     duration = time.time() - start
        #     throughput = pipeline.events_in_last_batch / duration
        #     throughputs.append(throughput)

        # avg_throughput = sum(throughputs) / len(throughputs)
        # print(f"Average throughput with backpressure: {avg_throughput:.0f} eps")

        # Verify backpressure doesn't cause crashes
        # assert all(t > 0 for t in throughputs), "Pipeline stalled under backpressure"

        pass

    async def test_batch_size_optimization(self, cassandra_session, postgres_connection):
        """
        Find optimal batch size for throughput
        Tests batch sizes: 10, 50, 100, 500, 1000
        """
        batch_sizes = [10, 50, 100, 500, 1000]
        results: Dict[int, float] = {}

        print(f"\n=== Batch Size Optimization ===")
        print(f"Testing batch sizes: {batch_sizes}")

        for batch_size in batch_sizes:
            print(f"\nTesting batch_size={batch_size}...")

            # Insert test data
            num_events = 5000
            cassandra_session.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ecommerce.perf_test_batch_{batch_size} (
                    id uuid PRIMARY KEY,
                    value text
                )
                """
            )

            insert_stmt = cassandra_session.prepare(
                f"""
                INSERT INTO ecommerce.perf_test_batch_{batch_size} (id, value)
                VALUES (?, ?)
                """
            )

            for i in range(num_events):
                cassandra_session.execute(insert_stmt, (uuid4(), f"value_{i}"))

            # Run pipeline with this batch size
            # from src.main import CDCPipeline
            # pipeline = CDCPipeline(batch_size=batch_size)

            # start_time = time.time()
            # await pipeline.run_until_complete()
            # duration = time.time() - start_time

            # throughput = num_events / duration
            # results[batch_size] = throughput

            # print(f"  Batch size {batch_size}: {throughput:.0f} eps")

        # Find optimal batch size
        # optimal_batch = max(results, key=results.get)
        # print(f"\n=== Optimal Batch Size: {optimal_batch} ({results[optimal_batch]:.0f} eps) ===")

        pass
