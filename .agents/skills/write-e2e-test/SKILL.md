---
name: write-e2e-test
description: Write, update, debug, or run Baserow end-to-end tests in e2e-tests using Playwright, the repo's e2e fixtures, page objects, Docker stack, and just e2e commands.
---

# Write Baserow E2E Tests

Use this skill when a task involves adding, fixing, reviewing, debugging, or
executing end-to-end tests in `e2e-tests`.

Canonical repo docs live in `docs/development/e2e-testing.md`. Read that file
again if commands or environment details may have changed.

## First Step

Before editing, identify the user-facing flow and inspect the closest existing
spec, fixture, and page object in the same area.

Useful searches:

- `find e2e-tests/tests -type f -name '*.spec.ts' | sort`
- `rg -n "test\\.describe|test\\(|test\\.before|@fast|@slow|@enterprise" e2e-tests/tests`
- `rg -n "class .*Page|async .*\\(" e2e-tests/pages e2e-tests/fixtures`
- `rg -n "getByRole|getByLabel|getByText|locator\\(" e2e-tests/tests e2e-tests/pages`

## Local Test Architecture

The suite uses Playwright with Nuxt test utilities:

- Specs live under `e2e-tests/tests/**`.
- Import `test` and `expect` from `e2e-tests/tests/baserowTest.ts` when the
  test should use the repo fixtures.
- Reuse API fixtures from `e2e-tests/fixtures/**` for setup instead of creating
  state through the UI when setup is not the behavior under test.
- Reuse or add page objects in `e2e-tests/pages/**` for repeated navigation or
  complex UI operations.
- The Playwright config is `e2e-tests/playwright.config.ts`; default projects
  are `chrome` and `firefox`, with `chrome` used by `yarn test`.

Important fixture behavior:

- `workspacePage` creates a fresh user and workspace, authenticates, suppresses
  the cookie notice, closes the AI sidebar, and cleans up with `removeAll()`.
- `builderPagePage` creates a builder and default page in that workspace.
- `automationWorkflowPage` creates an automation and default workflow.
- Staff-only setup can use `getStaffUser()` from `e2e-tests/fixtures/user.ts`,
  which logs in as `e2e@baserow.io` from the e2e database dump.

## Writing Tests

Prefer a focused test that proves one visible behavior or one integration
boundary.

1. Put the spec in the existing feature directory, for example
   `e2e-tests/tests/database/**`, `e2e-tests/tests/builder/**`, or
   `e2e-tests/tests/automation/**`.
2. Use API fixtures for initial data and reserve UI steps for the behavior being
   tested.
3. Use role, label, placeholder, and text locators when stable. Use CSS class
   locators when matching existing page objects or when the app has no better
   accessible hook.
4. Wait with Playwright assertions such as `await expect(locator).toBeVisible()`,
   `toHaveText()`, `toHaveURL()`, or `toHaveTitle()` instead of fixed sleeps.
5. If multiple tests share expensive setup, follow nearby specs that use
   `beforeAll` plus reset helpers, and use serial mode only when the shared
   state makes parallel execution unsafe.
6. For network-sensitive behavior, use `page.waitForResponse`,
   `page.waitForRequest`, or existing helpers in `e2e-tests/fixtures/network.ts`.

Keep `docs/testing/*-test-plan.md` files in sync when editing a spec that is
explicitly mapped to a test plan, such as grid view tests.

## Running Tests

Use root `just e2e` commands. They delegate to `e2e-tests/justfile`.

Full clean cycle:

```bash
just e2e run
```

Step-by-step:

```bash
just e2e build
just e2e up
just e2e test
```

Run a narrow target:

```bash
just e2e up
just e2e test tests/builder/builderPage.spec.ts
just e2e test tests/database/grid/
just e2e test --grep "login"
```

Debug:

```bash
just e2e up
just e2e test tests/path/to/spec.ts --headed
just e2e test tests/path/to/spec.ts --ui
just e2e test tests/path/to/spec.ts --trace on
just e2e logs
just e2e logs backend
just e2e logs frontend
just e2e logs celery
```

Important command behavior:

- `just e2e test` requires the e2e stack to already be running.
- `just e2e test` tears down the e2e containers when it exits, even for a
  narrow test.
- The default e2e URLs are frontend `http://localhost:3070` and backend
  `http://localhost:8070`.
- Override ports with `E2E_FRONTEND_PORT` and `E2E_BACKEND_PORT`, or set values
  in `e2e-tests/.env`.
- If migrations changed and the dump is stale, run `just e2e db-dump` and commit
  `e2e-tests/fixtures/e2e-db.dump`.

## Guardrails

- Do not use the deprecated `e2e-tests/run-e2e-tests-locally.sh` workflow unless
  the user explicitly asks to run against a manually managed dev environment.
- Do not create broad UI journeys when a fixture plus focused UI assertion proves
  the behavior.
- Do not use arbitrary `waitForTimeout` in specs. Existing page objects may have
  narrow compatibility sleeps; avoid adding new ones unless there is no better
  observable condition.
- Do not leave `test.only` or debug-only traces/headed settings in committed
  specs.
- Do not assume `page.title()` is immediately updated after navigation. For
  asynchronous public/builder page titles, use `await expect(page).toHaveTitle(...)`.
- Do not update non-English locale files while supporting an e2e test change.
