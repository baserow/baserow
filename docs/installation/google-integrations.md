# Google integration setup

Google integrations connect accounts for Gmail actions. They use Baserow's
[shared OAuth account integration](oauth-account-integrations.md), including sign-in,
reconnection, token refresh, permissions, and the lifecycle of copied connections.
Calendar actions, attachments, replies and sender aliases are not supported.

## Configure a Google client

1. Create a Google Cloud project and enable the **Gmail API**.
2. Configure the Google Auth Platform consent screen, audience and test users.
3. Create an OAuth client of type **Web application**.
4. Add the exact authorized redirect URI shown in the Google integration form:
   `<PUBLIC_WEB_FRONTEND_URL>/integrations/google/oauth-callback`.
   Use the frontend's public HTTPS origin. Localhost development may use HTTP.
5. Configure `BASEROW_GOOGLE_OAUTH_CLIENT_ID` and
   `BASEROW_GOOGLE_OAUTH_CLIENT_SECRET` on the backend and workers to offer the
   **Baserow client** option. Alternatively, select **Custom client** and enter
   a client ID and secret in each Google integration.
6. Save the integration, edit it again, and sign in through the shared account form.
   In a Gmail action, select the integration and grant sending permission when
   prompted. Check the account displayed before running the action.

Changing a Google integration's client configuration requires reconnecting it.
The shared form explains account switching, disconnecting, and how published and
other copies retain their connection. Its sign-in uses the shared endpoints under
`/api/integrations/oauth/google/`; the previous Google-specific callback and
endpoints are no longer used.

The Google adapter requests `openid` and `email` for account identity. Gmail actions
add only `https://www.googleapis.com/auth/gmail.send`, with incremental consent and
offline access. Declining that permission leaves Gmail unavailable until it is granted.
No sign-in starts during public action execution. The sender is the connected account,
and the action returns `id` and `threadId` for subsequent formulas.

## Hosted OAuth verification

`gmail.send` is a **sensitive** Google OAuth scope. An externally available hosted
client must complete Google's applicable verification before general use. Configure
verified domains, homepage, privacy policy and scopes in Google Auth Platform.
During testing, add test users. Testing-mode token expiry and Workspace administrator
policies may require reconnecting.

See Google's [OAuth web server guide](https://developers.google.com/identity/protocols/oauth2/web-server)
and [Gmail scope classifications](https://developers.google.com/workspace/gmail/api/auth/scopes).

## Live verification

Use a Google test account and a controlled recipient. Connect the account, grant
Gmail sending permission, and send Unicode content with To, Cc and Bcc. Check the
sender, delivery, plain/HTML rendering, and the returned message and thread IDs.
The service does not retry a timed-out send: delivery might already have occurred.
Review execution history before explicitly retrying an Automation action.
