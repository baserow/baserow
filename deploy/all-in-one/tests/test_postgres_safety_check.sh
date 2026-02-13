#!/usr/bin/env bash
set -Eeo pipefail

# test_postgres_safety_check.sh
#
# Tests for the PostgreSQL safety-check functions in postgres-safety-check.sh.
# These tests verify that:
#   - The data directory lock prevents concurrent access
#   - Dirty PostgreSQL shutdown states are detected and blocked
#   - Override environment variables work correctly
#   - Clean states allow normal startup
#
# Usage:  bash deploy/all-in-one/tests/test_postgres_safety_check.sh
#
# These tests do NOT require a running PostgreSQL instance. They use mock
# pg_controldata output and temporary directories to simulate scenarios.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAFETY_CHECK_SCRIPT="$SCRIPT_DIR/../supervisor/postgres-safety-check.sh"

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TEST_TMPDIR=""

# ── helpers ──────────────────────────────────────────────────────────────────

setup() {
    TEST_TMPDIR=$(mktemp -d)
    # Unset all override env vars so each test starts clean.
    unset BASEROW_DISABLE_LOCK_CHECK
    unset BASEROW_SKIP_PG_STATE_CHECK
    unset BASEROW_ALLOW_PG_RECOVERY
}

teardown() {
    rm -rf "$TEST_TMPDIR"
}

pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo "  PASS: $1"
}

fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo "  FAIL: $1"
    if [[ -n "${2:-}" ]]; then
        echo "        $2"
    fi
}

run_test() {
    local test_name="$1"
    TESTS_RUN=$((TESTS_RUN + 1))
    setup
    echo "Running: $test_name"
    # Run the test function; capture exit code.
    if "$test_name"; then
        : # test function reports pass/fail internally
    fi
    teardown
}

# Create a mock pg_controldata that returns a fixed cluster state.
# Usage: create_mock_pg_controldata <state_string>
create_mock_pg_controldata() {
    local state="$1"
    local mock_bin="$TEST_TMPDIR/bin"
    mkdir -p "$mock_bin"
    cat > "$mock_bin/pg_controldata" <<MOCK_EOF
#!/bin/bash
echo "pg_control version number:            1300"
echo "Catalog version number:               202107181"
echo "Database system identifier:           7123456789012345678"
echo "Database cluster state:               ${state}"
echo "pg_control last modified:             $(date)"
MOCK_EOF
    chmod +x "$mock_bin/pg_controldata"
    export PATH="$mock_bin:$PATH"
}

# Create a minimal fake PGDATA directory that looks initialised.
create_fake_pgdata() {
    local pgdata="$TEST_TMPDIR/postgres"
    mkdir -p "$pgdata"
    echo "15" > "$pgdata/PG_VERSION"
    touch "$pgdata/baserow_db_setup"
    echo "$pgdata"
}

# ── Lock tests ───────────────────────────────────────────────────────────────

test_lock_prevents_second_process() {
    source "$SAFETY_CHECK_SCRIPT"

    # First lock acquisition should succeed.
    acquire_data_dir_lock "$TEST_TMPDIR"
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        fail "First lock acquisition should succeed" "exit code: $rc"
        return
    fi

    # Second acquisition in a sub-shell should fail.
    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        acquire_data_dir_lock '$TEST_TMPDIR' 2>&1
    " 2>&1) && {
        fail "Second lock acquisition should have failed" "output: $output"
        return
    }

    if echo "$output" | grep -q "Another Baserow"; then
        pass "Lock prevents concurrent access with clear error message"
    else
        fail "Error message should mention 'Another Baserow'" "output: $output"
    fi
}

test_lock_disabled_by_env() {
    source "$SAFETY_CHECK_SCRIPT"

    # First, hold a lock.
    acquire_data_dir_lock "$TEST_TMPDIR"

    # Second acquisition with override should succeed (well, the check is
    # skipped, so it returns 0 regardless).
    local output
    output=$(bash -c "
        export BASEROW_DISABLE_LOCK_CHECK=yes
        source '$SAFETY_CHECK_SCRIPT'
        acquire_data_dir_lock '$TEST_TMPDIR' 2>&1
    " 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        pass "Lock check is skipped when BASEROW_DISABLE_LOCK_CHECK is set"
    else
        fail "Lock check should be skipped when BASEROW_DISABLE_LOCK_CHECK is set" "exit code: $rc"
    fi
}

test_lock_file_created() {
    source "$SAFETY_CHECK_SCRIPT"
    acquire_data_dir_lock "$TEST_TMPDIR"

    if [[ -f "$TEST_TMPDIR/.baserow.lock" ]]; then
        pass "Lock file is created in data directory"
    else
        fail "Lock file should exist after acquisition"
    fi
}

# ── Dirty shutdown detection tests ───────────────────────────────────────────

test_dirty_shutdown_in_production_blocks_startup() {
    create_mock_pg_controldata "in production"
    local pgdata
    pgdata=$(create_fake_pgdata)

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1) && {
        fail "Dirty shutdown (in production) should block startup"
        return
    }

    if echo "$output" | grep -q "not shut down cleanly"; then
        pass "Dirty shutdown (in production) detected and blocked with clear error"
    else
        fail "Error should mention 'not shut down cleanly'" "output: $output"
    fi
}

test_dirty_shutdown_in_crash_recovery_blocks_startup() {
    create_mock_pg_controldata "in crash recovery"
    local pgdata
    pgdata=$(create_fake_pgdata)

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1) && {
        fail "Dirty shutdown (in crash recovery) should block startup"
        return
    }

    if echo "$output" | grep -q "FATAL ERROR"; then
        pass "Dirty shutdown (in crash recovery) detected and blocked"
    else
        fail "Error should contain 'FATAL ERROR'" "output: $output"
    fi
}

test_dirty_shutdown_in_archive_recovery_blocks_startup() {
    create_mock_pg_controldata "in archive recovery"
    local pgdata
    pgdata=$(create_fake_pgdata)

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1) && {
        fail "Dirty shutdown (in archive recovery) should block startup"
        return
    }

    if echo "$output" | grep -q "FATAL ERROR"; then
        pass "Dirty shutdown (in archive recovery) detected and blocked"
    else
        fail "Error should contain 'FATAL ERROR'" "output: $output"
    fi
}

test_clean_shutdown_allows_startup() {
    create_mock_pg_controldata "shut down"
    local pgdata
    pgdata=$(create_fake_pgdata)

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        pass "Clean shutdown state allows normal startup"
    else
        fail "Clean shutdown should not block startup" "exit code: $rc, output: $output"
    fi
}

test_fresh_install_allows_startup() {
    # No PGDATA directory at all — first-time install.
    local pgdata="$TEST_TMPDIR/nonexistent_pgdata"

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        pass "Fresh install (no data directory) allows startup"
    else
        fail "Fresh install should not block startup" "exit code: $rc"
    fi
}

test_uninitialised_pgdata_allows_startup() {
    # Directory exists but no PG_VERSION — not yet initialised.
    local pgdata="$TEST_TMPDIR/postgres"
    mkdir -p "$pgdata"

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        pass "Uninitialised PGDATA (no PG_VERSION) allows startup"
    else
        fail "Uninitialised PGDATA should not block startup" "exit code: $rc"
    fi
}

test_recovery_override_allows_dirty_startup() {
    create_mock_pg_controldata "in production"
    local pgdata
    pgdata=$(create_fake_pgdata)

    local output
    output=$(bash -c "
        export BASEROW_ALLOW_PG_RECOVERY=yes
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        pass "BASEROW_ALLOW_PG_RECOVERY allows startup despite dirty state"
    else
        fail "Recovery override should allow startup" "exit code: $rc, output: $output"
    fi
}

test_skip_state_check_env_allows_dirty_startup() {
    create_mock_pg_controldata "in production"
    local pgdata
    pgdata=$(create_fake_pgdata)

    local output
    output=$(bash -c "
        export BASEROW_SKIP_PG_STATE_CHECK=yes
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        pass "BASEROW_SKIP_PG_STATE_CHECK skips the check entirely"
    else
        fail "Skip check env should bypass the check" "exit code: $rc"
    fi
}

test_error_message_includes_recovery_guidance() {
    create_mock_pg_controldata "in production"
    local pgdata
    pgdata=$(create_fake_pgdata)

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1) || true

    local checks_passed=true
    if ! echo "$output" | grep -q "BASEROW_ALLOW_PG_RECOVERY"; then
        fail "Error message should mention BASEROW_ALLOW_PG_RECOVERY"
        checks_passed=false
    fi
    if ! echo "$output" | grep -q "pg_resetwal"; then
        fail "Error message should mention pg_resetwal as last resort"
        checks_passed=false
    fi
    if ! echo "$output" | grep -q "force-killed\|docker kill\|SIGKILL"; then
        fail "Error message should explain common causes"
        checks_passed=false
    fi
    if [[ "$checks_passed" == "true" ]]; then
        pass "Error message includes recovery guidance, pg_resetwal warning, and causes"
    fi
}

test_lock_error_message_includes_guidance() {
    source "$SAFETY_CHECK_SCRIPT"
    acquire_data_dir_lock "$TEST_TMPDIR"

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        acquire_data_dir_lock '$TEST_TMPDIR' 2>&1
    " 2>&1) || true

    local checks_passed=true
    if ! echo "$output" | grep -q "docker stop"; then
        fail "Lock error should suggest docker stop"
        checks_passed=false
    fi
    if ! echo "$output" | grep -q "BASEROW_DISABLE_LOCK_CHECK"; then
        fail "Lock error should mention BASEROW_DISABLE_LOCK_CHECK override"
        checks_passed=false
    fi
    if [[ "$checks_passed" == "true" ]]; then
        pass "Lock error message includes actionable guidance"
    fi
}

# ── No-baserow-setup tests ──────────────────────────────────────────────────

test_no_baserow_setup_file_allows_startup() {
    # PG_VERSION exists but baserow_db_setup does not — Baserow never finished
    # initial setup, so there's nothing to protect yet.
    create_mock_pg_controldata "in production"
    local pgdata="$TEST_TMPDIR/postgres"
    mkdir -p "$pgdata"
    echo "15" > "$pgdata/PG_VERSION"
    # Deliberately do NOT touch baserow_db_setup

    local output
    output=$(bash -c "
        source '$SAFETY_CHECK_SCRIPT'
        check_postgres_clean_shutdown '$pgdata' 2>&1
    " 2>&1)
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        pass "Missing baserow_db_setup allows startup (initial setup not complete)"
    else
        fail "Should allow startup when baserow_db_setup doesn't exist" "exit code: $rc"
    fi
}

# ── Run all tests ────────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  PostgreSQL Safety Check Tests"
echo "========================================"
echo ""

# Lock tests
run_test test_lock_prevents_second_process
run_test test_lock_disabled_by_env
run_test test_lock_file_created
run_test test_lock_error_message_includes_guidance

# Dirty shutdown tests
run_test test_dirty_shutdown_in_production_blocks_startup
run_test test_dirty_shutdown_in_crash_recovery_blocks_startup
run_test test_dirty_shutdown_in_archive_recovery_blocks_startup
run_test test_clean_shutdown_allows_startup
run_test test_fresh_install_allows_startup
run_test test_uninitialised_pgdata_allows_startup
run_test test_recovery_override_allows_dirty_startup
run_test test_skip_state_check_env_allows_dirty_startup
run_test test_error_message_includes_recovery_guidance
run_test test_no_baserow_setup_file_allows_startup

echo ""
echo "========================================"
echo "  Results: $TESTS_PASSED/$TESTS_RUN passed, $TESTS_FAILED failed"
echo "========================================"
echo ""

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
exit 0
