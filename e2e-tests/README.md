# Baserow e2e tests

## Running the test suite

### How to run locally

For the first time:

```bash
cd e2e-tests

# This will install dependencies and wait for services
# to be up and running
./run-e2e-tests-locally.sh 
```

For any subsequent run without installing dependencies and waiting for
Baserow to run, make sure that `PUBLIC_WEB_FRONTEND_URL` and `PUBLIC_BACKEND_URL` env vars are set correctly (see `./run-e2e-tests-locally.sh`). After that, you can use
predefined entrypoints
in the `package.json`'s script section:

```bash
yarn run test

# for headed mode (with visible browser window)
yarn run test-headed
```

### How to get HTML test run report

To see HTML report of the test run, use the `--reporter=html`:

```bash
yarn run test --reporter=html

# You can always open the last report
yarn playwright show-report
```

### How to run with UI mode

Playwright offers UI mode (with `--ui`) that let's you select tests to run and shows
you detailed test execution:

```
yarn run test-headed --project=chrome --ui
```

### How to run using VSCode

To be able to run the tests using VSCode integrated test runner,
make sure to install [Playwright Test for VSCode](https://marketplace.visualstudio.com/items?itemName=ms-playwright.playwright) extension
and configure VSCode settings in your local `.vscode/settings.json` file:

```json
"playwright.env": {
  "PUBLIC_BACKEND_URL": "http://localhost:8000",
  "PUBLIC_WEB_FRONTEND_URL": "http://localhost:3000",
}
```

### How this runs in CI

All the CI does is essentially the following which you can run locally to reproduce
a CI run.

```bash
cd ..
./dev.sh build_only
cd e2e-tests
docker-compose up --build --exit-code-from e2e-tests
```

## Writing tests

### Using VSCode codegen

To use the Playwright codegen tool from VSCode:
- Make sure the Playwright extension is installed and tests can be run using VSCode test runner
- Start from already defined (even empty) test. This makes it possible to use fixtures or other setup code before starting recording new test steps
- Run the test using VSCode with the "Show browser" setting checked in the Playwright VSCode panel
- When the test run ends, the browser window will stay open
- Place the cursor at the end of the test code where new code should be written
- Now you can click on "Record at cursor" in the Playwright VSCode panel and start interacting with the page
- When done, refactor the code and make sure it runs correctly

### Using timeouts

Using timeouts is discouraged but there are situations where the test execution is too fast and the mechanism of waiting for an element to appear doesn't help. For example,
counting elements after some backend call.

If it is enough, increase the default timeout for standard element waiting:

```js
// for example
await expect(locator).toHaveCount(2, { timeout: 15000 })
```

Or introduce a timeout with a comment:

```js
// Explanation
await page.waitForTimeout(200)
```

## Debugging tests

### Options to debug tests when things go wrong

- Use VSCode integrated debugger to step through the code
- Use `--debug` option when running code on the command line
  - Use `await page.pause()` in tests to pause execution (like a breakpoint)
- Look at detailed HTML report or follow the traces in the UI mode (`--ui`)
- Examine final Playwright selector from any `Locator` object with `locator._selector`.
  - You can test any selector using `playwright.$$('here goes my selector')` function call in the browser's console during test runs.
    - This way it is possible to see how many and if any elements are selected on the page.
