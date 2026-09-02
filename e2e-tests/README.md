## How to run locally

```bash
cd e2e-tests
# This will do all the yarn installs for you
./run-e2e-tests-locally.sh 
# Once done you can easily just re-run the following:
yarn run test
```

## Environment variables

The suite runs two ways, and which mail variable applies depends on which.

| Variable | Used by | Meaning |
| --- | --- | --- |
| `E2E_MAIL_API_URL` | `./run-e2e-tests-locally.sh` and `yarn run test` | Where the tests read sent mail from. Defaults to `http://localhost:$BASEROW_MAILHOG_WEB_PORT`, falling back to port 8025. A dev stack started as alternate instance A or B publishes MailHog on 8035 or 8045 instead, so set `BASEROW_MAILHOG_WEB_PORT` (or this URL) to match the stack you are testing. |
| `E2E_MAIL_API_PORT` | `just e2e ...` | The host port the containerized stack publishes its own MailHog on. Defaults to 8075, and only needs changing when something else already listens there. The justfile builds `E2E_MAIL_API_URL` from it. |
| `E2E_HTTP_STUB_URL` | both | The endpoint the HTTP action tests call. The local runner starts httpbin in Docker when the backend allows private addresses, and falls back to the public httpbin.org otherwise. |
| `E2E_BUTTON_RATE_LIMIT` | both | How many external clicks a user gets per minute. The tests that click until they are refused are skipped when it is unset, since the runner cannot set it for a dev backend. |
