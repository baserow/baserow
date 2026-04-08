---
name: write-backend-unit-test
description: Write or update Baserow backend tests for core, premium, or enterprise code using pytest, Django, DRF APIClient, and the repo's shared fixture patterns.
---

# Write Baserow Backend Tests

Use this skill when a task is to add, fix, or extend a backend test in `backend/tests`, `premium/backend/tests`, or `enterprise/backend/tests`.

Do not invent a generic Django testing style. This repo already has strong pytest and fixture conventions. Start by finding the closest existing test in the same backend area and copy its setup shape.

## First Step

Before editing, identify the test target:

1. Handler, service, registry, or model logic
2. API view or serializer behavior
3. Signals, permissions, or settings-sensitive behavior
4. Query-count or performance-sensitive behavior
5. Premium or enterprise variant of one of the above

Then inspect the nearest existing test file in the same module area.

Useful searches:

- `rg --files backend/tests premium/backend/tests enterprise/backend/tests | rg 'test_.*\.py$'`
- `rg -n "@pytest\\.mark\\.django_db|api_client|data_fixture|premium_data_fixture|enterprise_data_fixture" backend/tests premium/backend/tests enterprise/backend/tests`
- `rg -n "pytest\\.raises|@patch\\(|override_settings|django_assert_num_queries" backend/tests premium/backend/tests enterprise/backend/tests`

## Tooling Used In This Repo

Current backend tests use:

- `pytest`
- `pytest-django`
- Django `reverse`
- DRF `APIClient` from the shared `api_client` fixture
- Shared fixtures from `backend/src/baserow/test_utils/pytest_conftest.py`
- Repo fixture builders such as `data_fixture`, `premium_data_fixture`, and `enterprise_data_fixture`

Important local files:

- `backend/src/baserow/test_utils/pytest_conftest.py`
- `premium/backend/tests/baserow_premium_tests/conftest.py`
- `enterprise/backend/tests/baserow_enterprise_tests/conftest.py`

`pytest_conftest.py` already provides `data_fixture`, `api_client`, `api_request_factory`, registry reset helpers, env helpers, and automatic signal deferral. Reuse those instead of building bespoke fixtures unless the nearby test already does something more specific.

## Choose The Right Pattern

### Handler, service, and model tests

For core business logic, keep the test direct:

1. Mark the test with `@pytest.mark.django_db` when it touches the database.
2. Build state with `data_fixture` or the premium or enterprise equivalent.
3. Instantiate the handler or call the target function directly.
4. Assert concrete persisted state, returned values, and raised exceptions.

Good examples:

- `backend/tests/baserow/core/test_core_handler.py`
- `backend/tests/baserow/core/service/test_service_handler.py`
- `enterprise/backend/tests/baserow_enterprise_tests/teams/test_team_handler.py`

Use `pytest.raises(...)` for error paths. Prefer asserting the specific domain exception over broad response or string checks when testing non-API code.

### API view tests

For API endpoints, match the common DRF style:

1. Create a user and token with `data_fixture.create_user_and_token()` when JWT auth is needed.
2. Build the URL with `reverse(...)`.
3. Call `api_client.get`, `post`, `patch`, or `delete`.
4. Pass auth as `HTTP_AUTHORIZATION=f"JWT {token}"`.
5. Assert both status code and the relevant response body fields.

Good examples:

- `backend/tests/baserow/api/groups/test_workspace_views.py`
- `backend/tests/baserow/contrib/database/api/rows/test_row_views.py`
- `premium/backend/tests/baserow_premium_tests/api/license/test_premium_license_views.py`

Prefer focused payload assertions. Only construct a large expected JSON object when the endpoint response shape is the behavior being tested.

### Signals and side effects

When the important behavior is that a signal or side effect fires:

1. Patch the exact function or signal send call used by the code.
2. Exercise the handler or API path.
3. Assert the mock was called with the expected domain objects or IDs.

Good examples:

- `backend/tests/baserow/core/test_core_handler.py`
- `enterprise/backend/tests/baserow_enterprise_tests/teams/test_team_receivers.py`

The shared test setup already defers many heavy async tasks. Do not add extra mocking for those unless the test specifically needs to assert the call.

### Settings, licenses, and query-count sensitive tests

Use the repo helpers already in use nearby:

1. Use `override_settings(...)` when the behavior is controlled by Django settings.
2. Use `django_assert_num_queries(...)` only when query count is part of the contract.
3. Use the premium or enterprise fixture helpers when the feature depends on licensing or edition-specific behavior.

Good examples:

- `backend/tests/baserow/config/test_read_replica_router.py`
- `premium/backend/tests/baserow_premium_tests/api/license/test_premium_license_views.py`
- `enterprise/backend/tests/baserow_enterprise_tests/sso/test_auth_provider_handler.py`

Do not turn ordinary behavior tests into performance tests.

## Fixtures And Data Setup

Prefer fixture builders over hand-rolling model graphs:

1. Use `data_fixture` for core backend objects.
2. Use `premium_data_fixture` in premium tests.
3. Use `enterprise_data_fixture` in enterprise tests.
4. Reuse `api_client` instead of instantiating `APIClient` manually.

If you need premium or enterprise-only entities, start by checking the corresponding `conftest.py` and nearby test files instead of guessing the fixture name.

## File Placement

Follow the existing test tree:

- Core: `backend/tests/baserow/**`
- Premium: `premium/backend/tests/baserow_premium_tests/**`
- Enterprise: `enterprise/backend/tests/baserow_enterprise_tests/**`

Keep the new test near the feature area rather than creating a new generic test module.

## Validation

Run the narrowest relevant test command first.

Examples:

- `just b test backend/tests/baserow/core/test_core_handler.py`
- `just b test backend/tests/baserow/api/groups/test_workspace_views.py`
- `just b test premium/backend/tests/baserow_premium_tests/api/license/test_premium_license_views.py`
- `just b test enterprise/backend/tests/baserow_enterprise_tests/teams/test_team_handler.py`

If you changed settings-sensitive or query-count-sensitive tests, check the exact failure instead of weakening the assertion immediately.

## Guardrails

- Do not introduce `unittest.TestCase` or Django `TestCase` patterns when the repo already uses plain pytest functions.
- Do not manually construct large object graphs if `data_fixture` already provides the needed factory.
- Do not over-mock core handlers, models, or registries when a focused real-object test is practical.
- Do not skip `@pytest.mark.django_db` on database-touching tests.
- Do not use broad API assertions when the behavior can be proved with a few targeted fields.
- Do not mix core, premium, and enterprise fixture styles in the same file unless the existing test pattern already does that.
