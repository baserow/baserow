# Development environment with read replicas

In order to test the PostgreSQL read replicas that can be configured, it's needed to
run the development environment with read replicas. This guide explains which changes
to made specifically.

## Docker compose

Replace the first part of your `docker-compose.dev.yml` with the following:

```
services:
  db:
    image: pgvector/pgvector:pg13
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      POSTGRES_USER: ${DATABASE_USER:-baserow}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:?}
      POSTGRES_DB: ${DATABASE_NAME:-baserow}
    volumes:
      - pgdata-primary:/var/lib/postgresql/data
      - ./docs/development/init/primary-init.sh:/docker-entrypoint-initdb.d/primary-init.sh:ro
    command: >
      postgres -c wal_level=replica
               -c max_wal_senders=10
               -c wal_keep_segments=64
               -c hot_standby=on
               -c listen_addresses='*'
    networks:
      - local

  db-replica-1:
    image: pgvector/pgvector:pg13
    ports:
      - "127.0.0.1:5433:5432"
    environment:
      POSTGRES_USER: ${DATABASE_USER:-baserow}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:?}
      REPLICATION_PASSWORD: ${REPLICATION_PASSWORD:-replicatorpass}
    volumes:
      - pgdata-replica-1:/var/lib/postgresql/data
      - ./docs/development/init/replica-entrypoint.sh:/scripts/replica-entrypoint.sh:ro
    user: postgres
    depends_on:
      - db
    entrypoint: [ "/scripts/replica-entrypoint.sh" ]
    networks:
      - local

  db-replica-2:
    image: pgvector/pgvector:pg13
    ports:
      - "127.0.0.1:5434:5432"
    environment:
      POSTGRES_USER: ${DATABASE_USER:-baserow}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:?}
      REPLICATION_PASSWORD: ${REPLICATION_PASSWORD:-replicatorpass}
    volumes:
      - pgdata-replica-2:/var/lib/postgresql/data
      - ./docs/development/init/replica-entrypoint.sh:/scripts/replica-entrypoint.sh:ro
    user: postgres
    depends_on:
      - db
    entrypoint: [ "/scripts/replica-entrypoint.sh" ]
    networks:
      - local
```

Add the following to the end of the file:

```
volumes:
  pgdata-primary:
  pgdata-replica-1:
  pgdata-replica-2:
```

Then execute:

```
chmod +x ./docs/development/init/primary-init.sh
chmod +x ./docs/development/init/replica-entrypoint.sh
```

Restart your dev environment and observe that the read-only replications are accessible.
They're available on port `5433` and `5434` with the same password you're using the
same username and password as the writer `db`.

## Baserow configuration

Add the following to your `.env` file and restart your dev server. This will configure
Baserow to use the above read-only replications for read queries.

```
DATABASE_READ_1_NAME="baserow"
DATABASE_READ_1_USER="baserow"
DATABASE_READ_1_PASSWORD="baserow"
DATABASE_READ_1_HOST="db-replica-1"
DATABASE_READ_1_PORT="5432"
DATABASE_READ_2_NAME="baserow"
DATABASE_READ_2_USER="baserow"
DATABASE_READ_2_PASSWORD="baserow"
DATABASE_READ_2_HOST="db-replica-2"
DATABASE_READ_2_PORT="5432"
```
