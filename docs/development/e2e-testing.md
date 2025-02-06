# End-to-end testing

Baserow comes with end-to-end test suite in the `e2e-tests` folder. The test suite
uses [Playwright](https://playwright.dev/) testing tool to run UI tests against a
running Baserow instance using one or multiple browsers.

## When and what to e2e test

As of February 2023 the e2e test suite is brand new, we recommend you add any e2e
tests you think make sense. Some ideas on what to test:
1. Complicated multiservice UX flows like duplicating a database
2. Complicated frontend code that is hard to test with unit tests
3. The serialization boundary between the frontend client and backend api
4. Critical features that often accidentally break or features that often break in
   other browsers, and we don't notice.

## Installation and running locally

You'll need Node.js to run the end-to-end test suite locally. Using [nvm](https://github.com/nvm-sh/nvm),
it can be installed with:
```bash
nvm install v<version>
```

Replace `<version>` with a supported Node.js version listed in
`baserow/docs/installation/supported.md`.

To run the end-to-end tests:
```bash
# Startup your local env which will be tested
$ ./dev.sh
$ cd e2e-tests
# The below script installs the e2e test package, waits for your dev env to be healthy
# and then runs the tests.
$ ./run-e2e-tests-locally.sh 
# After which you can manually re-run the tests with various manual commands: 
yarn test # headless
yarn test-headed
yarn test-ui # starts the UI mode. Best way to debug you tests.
yarn codegen # Helps to generate tests directly in a browsers. Use it as inspiration; 
             # the skeleton can be used, but some of its generated code is bad. 
             # Tweak it yourself after use.
```

`yarn test` and `yarn test-*` will run all tests in Chrome.

## Configuration

Besides Playwright configuration defined in `e2e-tests/playwright.config.ts` you can set
environment variables to target a Baserow instance on any URL
with `PUBLIC_WEB_FRONTEND_URL` and `PUBLIC_BACKEND_URL`. You can also
use `e2e-tests/.env` file to do so, see `e2e-tests/.env-example`.
