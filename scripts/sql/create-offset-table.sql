-- Create CDC Offsets Table for Postgres and TimescaleDB
-- Tracks replication progress for exactly-once delivery

CREATE TABLE IF NOT EXISTS cdc_offsets (
    offset_id UUID PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    keyspace VARCHAR(255) NOT NULL,
    partition_id BIGINT NOT NULL,
    destination VARCHAR(50) NOT NULL,
    commitlog_file VARCHAR(500) NOT NULL,
    commitlog_position BIGINT NOT NULL,
    last_event_timestamp_micros BIGINT NOT NULL,
    last_committed_at TIMESTAMPTZ DEFAULT NOW(),
    events_replicated_count BIGINT DEFAULT 0,

    -- Unique constraint for each partition+destination combination
    UNIQUE(table_name, keyspace, partition_id, destination)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_cdc_offsets_table_dest
    ON cdc_offsets(table_name, keyspace, destination);

CREATE INDEX IF NOT EXISTS idx_cdc_offsets_timestamp
    ON cdc_offsets(last_event_timestamp_micros DESC);

-- Add comments
COMMENT ON TABLE cdc_offsets IS 'Tracks CDC replication offsets for exactly-once delivery';
COMMENT ON COLUMN cdc_offsets.offset_id IS 'Unique identifier for this offset record';
COMMENT ON COLUMN cdc_offsets.table_name IS 'Cassandra table being replicated';
COMMENT ON COLUMN cdc_offsets.keyspace IS 'Cassandra keyspace';
COMMENT ON COLUMN cdc_offsets.partition_id IS 'Cassandra partition token range identifier';
COMMENT ON COLUMN cdc_offsets.destination IS 'Target warehouse (POSTGRES, CLICKHOUSE, TIMESCALEDB)';
COMMENT ON COLUMN cdc_offsets.commitlog_file IS 'Last processed commitlog file';
COMMENT ON COLUMN cdc_offsets.commitlog_position IS 'Byte position in commitlog file';
COMMENT ON COLUMN cdc_offsets.last_event_timestamp_micros IS 'Timestamp of last replicated event';
COMMENT ON COLUMN cdc_offsets.last_committed_at IS 'When this offset was last committed';
COMMENT ON COLUMN cdc_offsets.events_replicated_count IS 'Total events replicated for this partition';
