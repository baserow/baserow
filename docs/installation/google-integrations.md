# Google integration setup

Google integrations belong to an application. Create separate integrations for separate
Google accounts; Gmail actions that select the same integration share its connection.
A reconnect must use the same Google account. To change accounts, create a new
integration. Calendar actions, attachments, replies and sender aliases are not supported.

## Configure a client

1. Create a Google Cloud project and enable the **Gmail API**.
2. Configure the Google Auth Platform consent screen, audience and test users.
3. Create an OAuth client of type **Web application**.
4. Add the authorized redirect URI shown in the Google integration form. It is
   `PUBLIC_WEB_FRONTEND_URL/google-oauth-callback`, with no trailing slash. Use the
   frontend's public HTTPS origin, not the backend URL. Localhost development may use
   HTTP. Register each deployment's URI exactly.
5. Either configure `BASEROW_GOOGLE_OAUTH_CLIENT_ID` and
   `BASEROW_GOOGLE_OAUTH_CLIENT_SECRET` on the backend and workers, then choose
   **Baserow client**, or choose **Custom client** and enter the client ID and secret
   in each integration. Without a global client, use a custom client.
6. Save the integration, edit it again and choose **Connect Google**. For a Gmail
   action, choose its integration and grant the additional sending permission when
   prompted. Check the connected account before running the action.

The flow requests `openid` and `email` to identify the account, and Gmail actions
request only `https://www.googleapis.com/auth/gmail.send` for sending. Consent is
incremental; declining the sending scope leaves the connection unusable for Gmail
until that scope is granted. No Google authorization starts while a public action runs.
The sender is always the connected account. The result contains `id` and `threadId`,
which subsequent formulas can reference.

## Hosted OAuth verification

`gmail.send` is a **sensitive** Google OAuth scope. An externally available hosted
client must complete Google's applicable OAuth app verification before general use.
Configure verified domains, homepage, privacy policy and the requested scopes in
Google Auth Platform. During testing, add test users; Google's testing-mode token
expiry and Workspace administrator policies may require users to reconnect.
See Google's [OAuth web server guide](https://developers.google.com/identity/protocols/oauth2/web-server)
and [Gmail scope classifications](https://developers.google.com/workspace/gmail/api/auth/scopes).

## Connection lifecycle

Tokens and custom client secrets are encrypted in the database. API responses and
exports do not contain them. Imported and duplicated applications need a fresh
connection. Published actions reference the original integration's credentials, so
local disconnect disables those actions too. Disconnect does not revoke Google's
grant globally; users can also remove access through their Google account settings.
Changing client configuration requires reconnecting.

Refreshes are serialized per connection. Temporary Google failures preserve the
refresh token, while revoked authorization requires reconnecting. Gmail sends are
never retried inside the service after a timeout: delivery might already have occurred.
Review execution history before explicitly retrying an Automation action.

## Live verification

Use a Google test account and a controlled recipient. Connect the account, grant
Gmail send permission, then send a Unicode subject and body with To, Cc and Bcc.
Check delivery, sender identity, HTML/plain rendering and the downstream message and
thread IDs. Disconnect and confirm that draft and published actions request a
reconnection. Never put OAuth secrets or tokens in source control or test logs.
