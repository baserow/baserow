# Slack stub

What the e2e stack answers `chat.postMessage` with, served by WireMock from this
directory mounted at `/home/wiremock`. The backend is pointed at it through
`BASEROW_INTEGRATIONS_SLACK_API_URL`, and the Slack e2e test checks that the
canned `ts` below is what a click writes into the row.
