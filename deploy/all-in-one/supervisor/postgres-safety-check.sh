#!/usr/bin/env bash
set -Eeo pipefail

# postgres-safety-check.sh
#
# Safety checks for the embedded PostgreSQL data directory.
# Prevents two common causes of database corruption:
#   1. Multiple containers using the same data volume simultaneously
#   2. Starting PostgreSQL after an unclean shutdown (which can cause PANIC errors)
#
# This script is sourced by baserow.sh and start.sh to reuse its functions.

BASEROW_LOCK_FD=200

# Acquire an exclusive flock on the data directory.
# The lock is held by the file descriptor and automatically released when the
# process (and all its exec'd children) exit -- even on SIGKILL.
#
# Usage: acquire_data_dir_lock "$DATA_DIR"
# Returns 0 on success, exits with error on failure.
acquire_data_dir_lock() {
    local data_dir="${1:?acquire_data_dir_lock requires DATA_DIR}"
    local lock_file="$data_dir/.baserow.lock"

    if [[ -n "${BASEROW_DISABLE_LOCK_CHECK:-}" ]]; then
        echo "WARNING: Data directory lock check is disabled (BASEROW_DISABLE_LOCK_CHECK is set)." >&2
        echo "WARNING: Running multiple containers on the same data volume WILL corrupt your database." >&2
        return 0
    fi

    # Open the lock file on our chosen FD. The FD is inherited through exec calls,
    # so supervisord (and its children) keep the lock alive.
    eval "exec ${BASEROW_LOCK_FD}>\"$lock_file\""

    if ! flock -n "$BASEROW_LOCK_FD"; then
        cat >&2 <<'EOF'

================================================================================
FATAL ERROR: Another Baserow container is using this data directory
================================================================================

Another Baserow process currently holds an exclusive lock on this data
directory. Running multiple containers against the same data volume WILL
corrupt your PostgreSQL database.

To fix this:

  1. Find and stop ALL other Baserow containers using this volume:

       docker ps | grep baserow
       docker stop <container_id>

  2. Wait for the other container to fully shut down.

  3. Start this container again. Only ONE container may use a data volume
     at a time.

If you are certain no other container is running (e.g. after a host reboot),
the lock file may be stale. Remove it and try again:

    docker run --rm -v <your_volume>:/baserow/data busybox \
        rm /baserow/data/.baserow.lock

To disable this check entirely (DANGEROUS — risks database corruption):

    -e BASEROW_DISABLE_LOCK_CHECK=yes

================================================================================

EOF
        exit 1
    fi

    # Write our PID and hostname into the lock file for diagnostics.
    echo "pid=$$ host=$(hostname) date=$(date -Iseconds)" >&${BASEROW_LOCK_FD}
    return 0
}

# Check whether PostgreSQL was shut down cleanly by inspecting pg_controldata.
#
# Usage: check_postgres_clean_shutdown "$PGDATA"
# Returns 0 if safe to start, exits with error if unclean.
check_postgres_clean_shutdown() {
    local pgdata="${1:?check_postgres_clean_shutdown requires PGDATA}"

    if [[ -n "${BASEROW_SKIP_PG_STATE_CHECK:-}" ]]; then
        echo "WARNING: PostgreSQL shutdown state check is disabled (BASEROW_SKIP_PG_STATE_CHECK is set)." >&2
        return 0
    fi

    # Nothing to check if the data directory doesn't exist yet or has never
    # been initialised by Baserow.
    if [[ ! -d "$pgdata" || ! -f "$pgdata/PG_VERSION" ]]; then
        return 0
    fi
    if [[ ! -f "$pgdata/baserow_db_setup" ]]; then
        return 0
    fi

    # pg_controldata reads the pg_control file and reports the cluster state.
    local cluster_state
    cluster_state=$(pg_controldata "$pgdata" 2>/dev/null \
        | grep "Database cluster state" \
        | sed 's/.*:[[:space:]]*//' || true)

    if [[ -z "$cluster_state" ]]; then
        # Could not determine state — let PostgreSQL handle it.
        return 0
    fi

    case "$cluster_state" in
        "shut down"|"shut down in recovery")
            # Clean shutdown — safe to start.
            return 0
            ;;
        "in production"|"in archive recovery"|"in crash recovery")
            # Unclean shutdown detected.
            if [[ -n "${BASEROW_ALLOW_PG_RECOVERY:-}" ]]; then
                cat >&2 <<EOF

================================================================================
WARNING: PostgreSQL was not shut down cleanly
================================================================================

Database cluster state: ${cluster_state}

BASEROW_ALLOW_PG_RECOVERY is set, so Baserow will attempt to start PostgreSQL
and let it perform crash recovery automatically. This usually works, but in
rare cases PostgreSQL may fail with:

    PANIC: could not locate a valid checkpoint record

If that happens, see the error guidance below for recovery steps.

================================================================================

EOF
                return 0
            fi

            cat >&2 <<EOF

================================================================================
FATAL ERROR: PostgreSQL was not shut down cleanly
================================================================================

Database cluster state: ${cluster_state}

This typically happens when:
  - The container was force-killed (docker kill, SIGKILL, OOM-kill)
  - The host machine crashed or lost power
  - Multiple containers were writing to the same data volume

Starting PostgreSQL in this state risks a PANIC error:

    PANIC: could not locate a valid checkpoint record

RECOMMENDED: Allow PostgreSQL to attempt automatic crash recovery by setting:

    -e BASEROW_ALLOW_PG_RECOVERY=yes

This is safe in most cases. PostgreSQL will replay its write-ahead log and
recover to a consistent state.

LAST RESORT: If automatic recovery fails, you can reset the write-ahead log.
WARNING — this may cause data loss:

    docker run --rm -it -v <your_volume>:/baserow/data baserow/baserow \\
      backend-cmd bash -c \\
      "su postgres -c '/usr/lib/postgresql/\$POSTGRES_VERSION/bin/pg_resetwal -f /baserow/data/postgres'"

To skip this safety check entirely (NOT RECOMMENDED):

    -e BASEROW_SKIP_PG_STATE_CHECK=yes

================================================================================

EOF
            exit 1
            ;;
        *)
            # Unknown state — let PostgreSQL decide.
            return 0
            ;;
    esac
}
