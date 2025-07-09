#!/bin/bash
set -e

echo "[replica] Waiting for primary database to be ready..."
until pg_isready -h db -p 5432 -U replicator; do
  sleep 2
done

echo "[replica] Configuring pgpass..."
echo "db:5432:replication:replicator:${REPLICATION_PASSWORD}" > ~/.pgpass
chmod 600 ~/.pgpass

echo "[replica] Starting base backup from primary..."
rm -rf /var/lib/postgresql/data/*
pg_basebackup -h db -U replicator -D /var/lib/postgresql/data -Fp -Xs -P -R

echo "[replica] Fixing ownership..."
chown -R postgres:postgres /var/lib/postgresql/data
chmod 0700 /var/lib/postgresql/data

echo "primary_conninfo = 'host=db port=5432 user=replicator password=${REPLICATION_PASSWORD}'" >> /var/lib/postgresql/data/postgresql.auto.conf
echo "hot_standby = on" >> /var/lib/postgresql/data/postgresql.conf

echo "[replica] Starting PostgreSQL..."
exec postgres
