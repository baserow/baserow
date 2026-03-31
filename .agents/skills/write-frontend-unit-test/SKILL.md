---
name: Write Frontend Unit Test
description: Write or update Baserow frontend unit tests for core, premium, or enterprise code using the repo's existing Vitest, Nuxt, Vue Test Utils, TestApp, and snapshot patterns.
version: 1.0.0
---

# Write Baserow Frontend Unit Tests

Use this skill when a task is to add, fix, or extend a frontend unit test in `web-frontend`, `premium/web-frontend`, or `enterprise/web-frontend`.

Do not invent a generic Vue testing style. This repo already has established patterns. Start by finding the closest existing spec and copy its setup shape.

## First Step

Before editing, identify the test target:

1. Pure utility or parser function
2. Vuex store logic
3. Vue component mounted with the shared app context
4. Nuxt/Vue 3 component mounted directly with `mountSuspended`
5. Premium or enterprise variant of one of the above

Then inspect the nearest existing spec in the same module area.

Useful searches:

- `rg --files web-frontend/test premium/web-frontend/test enterprise/web-frontend/test | rg '\.spec\.'`
- `rg -n "new TestApp\\(|new PremiumTestApp\\(|mountSuspended\\(" web-frontend/test premium/web-frontend/test enterprise/web-frontend/test`
- `rg -n "toMatchSnapshot\\(|vi\\.fn\\(|vi\\.spyOn\\(" web-frontend/test premium/web-frontend/test enterprise/web-frontend/test`

## Tooling Used In This Repo

Current frontend unit tests use:

- `vitest` for `describe`, `test`, `expect`, `vi`
- `@vue/test-utils`
- `@nuxt/test-utils/runtime` with `mountSuspended`
- Repo helpers such as `TestApp`, `PremiumTestApp`, `MockServer`, and fixtures under `web-frontend/test`
- Snapshot assertions for rendered HTML when the component output matters

Important local files:

- `web-frontend/vitest.setup.ts`
- `web-frontend/test/helpers/testApp.js`
- `premium/web-frontend/test/helpers/premiumTestApp.js`

`vitest.setup.ts` already mocks i18n, UUID generation, and `WebSocket`. Reuse that environment instead of re-mocking those globally in each spec.

## Choose The Right Pattern

### Pure utility tests

For functions in `modules/*/utils/**`, keep the test simple:

1. Import the function directly.
2. Use plain inputs and deterministic assertions.
3. Prefer `toStrictEqual`, `toBe`, or explicit formatted objects over snapshots.

Good examples:

- `web-frontend/test/unit/core/utils/date.spec.js`
- `web-frontend/test/unit/core/utils/string.spec.js`

### Store tests

For Vuex store behavior, prefer `TestApp` unless the existing spec clearly uses a temporary local store:

1. Create `testApp = new TestApp()` in `beforeEach`.
2. Read `store = testApp.store`.
3. Seed state through store actions or the mock server.
4. Always `await testApp.afterEach()` in `afterEach`.

Good examples:

- `web-frontend/test/unit/core/store/auth.spec.js`
- `web-frontend/test/unit/builder/store/dataSource.spec.js`

If the code lives in premium and needs premium-only auth/license behavior, use `PremiumTestApp`.

### Shared app component tests

For many components, especially older patterns or components coupled to store, router, registry, or client behavior:

1. Create `testApp = new TestApp()` or `new PremiumTestApp()`.
2. Mount with `testApp.mount(Component, { props, propsData, slots, listeners, global })`.
3. Prefer the existing helper in the file, for example `mountComponent(...)`.
4. Clean up with `await testApp.afterEach()`.

`TestApp.mount` supports both `props` and legacy `propsData`, and converts `listeners` into Vue 3 event props. Match the nearby spec instead of rewriting all setup.

Good examples:

- `web-frontend/test/unit/core/components/dropdown.spec.js`
- `premium/web-frontend/test/unit/premium/view/calendar/calendarView.spec.js`

### Direct `mountSuspended` component tests

For newer Nuxt/Vue 3 component tests that do not need the full helper wrapper:

1. Use `const testApp = useNuxtApp()` in `beforeEach` if the component expects injected app/store context.
2. Mount with `mountSuspended(Component, { props, slots, global: { provide, stubs, mocks } })`.
3. Provide injected dependencies explicitly.

Good examples:

- `web-frontend/test/unit/builder/components/elements/components/HeadingElement.spec.js`

## Assertions

Prefer the narrowest assertion that proves behavior:

- Use `toStrictEqual` or `toEqual` for transformed data and store state.
- Use `toBe` for scalar values.
- Use `vi.fn()` and `vi.spyOn()` for event handlers and method calls.
- Use snapshots for rendered markup where the repo already uses them.

Do not default to snapshots for pure logic.

When asserting reactive store objects, this repo sometimes normalizes them with:

```js
JSON.parse(JSON.stringify(value))
```

Use that only when the nearby test does it for Vue reactivity serialization issues.

Don't assert internals, always assert visible result in the DOM. For instance don't
use

```js
expect(wrapper.vm.values.use_instance_smtp_settings).toBe(false) # BAD
```

Don't directly use vm properties.

## Mocking And Fixtures

Prefer repo helpers over bespoke mocks:

1. Use `testApp.mockServer` when the behavior depends on store-backed API calls.
2. Use fixtures under `web-frontend/test/fixtures` and premium or enterprise fixture folders when suitable.
3. Use `testApp.dontFailOnErrorResponses()` only when the test intentionally exercises failing responses.

Do not build a large custom mock environment if `TestApp` already provides the needed app, client, registry, router, and store wiring.

## File Placement

Follow the existing test tree:

- Core: `web-frontend/test/unit/...`
- Premium: `premium/web-frontend/test/unit/...`
- Enterprise: `enterprise/web-frontend/test/unit/...`

Keep the spec near the feature area rather than creating a new generic test folder.

## Validation

Run the narrowest relevant test command first.

Examples:

- `just f yarn test:core --run test/unit/core/components/dropdown.spec.js`
- `just f yarn test:core --run test/unit/core/store/auth.spec.js`
- `just f yarn test:premium --run ../premium/web-frontend/test/unit/premium/view/calendar/calendarView.spec.js`
- `just f yarn test:enterprise --run ../enterprise/web-frontend/test/unit/enterprise/plugins.spec.js`

If a snapshot changes intentionally, review the diff instead of blindly accepting it.

## Guardrails

- Do not introduce Jest APIs. Use Vitest APIs already present in the repo.
- Do not add a standalone mount helper when `TestApp` or `PremiumTestApp` already fits.
- Do not over-mock store, router, or client dependencies if the real test helpers can provide them.
- Do not mix unrelated styles in one file. Match the nearest local spec.
- Do not leave out `afterEach` cleanup when using `TestApp` or `PremiumTestApp`.
- Do not create broad integration-style tests when a focused unit test is enough.
