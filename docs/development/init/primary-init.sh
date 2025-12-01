#!/bin/bash
set -e

echo "[primary-init] Creating replication user..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '${REPLICATION_PASSWORD:-replicatorpass}';
EOSQL

echo "[primary-init] Appending replication rule to pg_hba.conf..."
echo "host replication replicator 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"
