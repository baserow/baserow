# Google integration setup

Google integrations connect accounts for Gmail actions. They use Baserow's
[shared OAuth account integration](oauth-account-integrations.md), including sign-in,
reconnection, token refresh, permissions, and the lifecycle of copied connections.
Calendar actions, attachments, replies and sender aliases are not supported.

## Before you start

Use a Google account that you can add as a test user. The account used to create the
Cloud project can have a non-Gmail email address, but the account used to send mail
must have Gmail enabled, either through Gmail or Google Workspace. Google's
[Gmail quickstart](https://developers.google.com/workspace/gmail/api/quickstart/js)
lists this requirement.

You will create an **OAuth client ID** and a **client secret**. Baserow uses these
credentials to request permission from the account that signs in. You do not need
to create an API key or a service account for this integration.

## Create a Google Cloud project and enable Gmail

1. Open the [Google Cloud console](https://console.cloud.google.com/).
   Start from the console rather than the optional Google Cloud free-trial signup.
2. Open the project selector at the top of the page and choose **New project**.
3. Enter a name such as `Baserow Gmail Test`, then create the project.
4. Select that project in the project selector. Keep it selected for the following
   configuration steps.
5. Open **APIs & Services → Library**, search for **Gmail API**, open it and click
   **Enable**. If the page offers **Manage**, it is already enabled.

## Configure the consent screen and test users

1. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview).
   Click **Get started** if the project has not been configured yet.
2. Under **Branding**, enter an application name such as `Baserow Test`, choose
   your user support email, and complete the contact information.
3. For testing with personal Google accounts, choose the **External** audience.
   Keep the application in **Testing** rather than publishing it for general use.
4. Under **Audience → Test users**, add the Google account you will sign in with
   from Baserow. This may differ from the account that owns the Cloud project.
5. Under **Data Access → Add or remove scopes**, add:
   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/gmail.send`
6. Save the configuration. Do not add Calendar or mailbox-reading scopes for the
   Gmail send action.

Google describes these settings in its
[consent screen configuration guide](https://developers.google.com/workspace/guides/configure-oauth-consent).

## Create the OAuth web client

1. In **Google Auth Platform → Clients**, click **Create client**.
2. Choose **Web application** as the application type and enter a name such as
   `Baserow local`.
3. Under **Authorized redirect URIs**, click **Add URI** and enter:

   ```text
   <PUBLIC_WEB_FRONTEND_URL>/integrations/google/oauth-callback
   ```

   Replace the placeholder with your frontend's public origin. For example, if
   Baserow runs at `http://localhost:22081`, enter:

   ```text
   http://localhost:22081/integrations/google/oauth-callback
   ```

   The Google integration form also displays the exact URI for the installation.
   Register the frontend URI, including its port, path and scheme, with no trailing
   slash. Use HTTPS for deployed installations; localhost development can use HTTP.
4. Click **Create** and save the **Client ID** and **Client secret** securely.
   Enter the secret only in your local configuration or integration form, not in
   chat messages, screenshots or source control.

See Google's [credential creation guide](https://developers.google.com/workspace/guides/create-credentials)
for the web-client configuration.

## Connect the account in Baserow

For a local test, use a custom client:

1. Open a Baserow Automation or Application Builder application, then open its
   **Integrations** settings. Database button actions also offer integration
   creation and editing from their integration dropdown.
2. Add a **Google** integration and give it a recognizable name.
3. Choose **Custom client**, then paste the **Client ID** and **Client secret**
   from Google into the corresponding fields.
4. Save the integration, then reopen it. The client must be saved before signing in.
5. Click the Google sign-in button. Allow the popup if your browser blocks it.
6. Sign in with the account added under **Test users**, and review the permissions.
7. After the popup returns to Baserow, check the displayed account and its connected
   status. An identity-only connection does not yet authorize sending Gmail messages.

To share a client across the installation instead, configure
`BASEROW_GOOGLE_OAUTH_CLIENT_ID` and `BASEROW_GOOGLE_OAUTH_CLIENT_SECRET` on the
backend and workers, restart them, and choose **Baserow client** in the integration.
Builders do not need to enter the installation's secret in each integration.

## Test a Gmail action

1. Add a **Gmail send email** action to an Automation workflow, an Application
   Builder workflow, or a Database button field.
2. Select the connected Google integration.
3. If Baserow asks for Gmail sending permission, sign in through the action's
   account form and grant that permission.
4. Use an address you control as the recipient, enter a subject and body, and run
   the action. The sender is the connected Google account.
5. Check the recipient's inbox and spam folder. A successful action returns `id`
   and `threadId`, which later formulas can use.
6. To exercise the other composer fields, repeat with Unicode content, optional
   Cc/Bcc recipients, and plain text or HTML bodies.

The service does not retry a timed-out send: delivery might already have occurred.
Review execution history before explicitly retrying an Automation action.

## Troubleshooting the connection

| Symptom | What to check |
| --- | --- |
| Google reports `redirect_uri_mismatch` | Compare the URI registered in Google with the URI shown in Baserow. Scheme, host, port, path and trailing slash must match exactly. |
| Google refuses access while the app is in Testing | Add the account being used under **Audience → Test users** in the same Cloud project. A Workspace administrator may also need to approve access. |
| Baserow says Google is not configured | For a custom client, save both credentials and reopen the integration. For the Baserow client, configure the backend and worker environment variables. |
| The account connects but Gmail sending is unavailable | Grant the sending permission from the Gmail action and confirm the connected account has Gmail enabled. |
| The popup does not open | Allow popups for your Baserow origin, then start sign-in again. |

## Connection behavior

Changing a Google integration's client configuration requires reconnecting it.
The [shared account guide](oauth-account-integrations.md) explains account switching,
disconnecting, and how published and other copies retain their connection.

Gmail permission is requested incrementally. Declining it leaves Gmail sending
unavailable until it is granted. No sign-in starts during public action execution.

## Hosted OAuth verification

`gmail.send` is a **sensitive** Google OAuth scope. An externally available hosted
client must complete Google's applicable verification before general use. Configure
verified domains, homepage, privacy policy and scopes in Google Auth Platform.
During testing, add test users. Testing-mode token expiry and Workspace administrator
policies may require reconnecting.

See Google's [OAuth web server guide](https://developers.google.com/identity/protocols/oauth2/web-server)
and [Gmail scope classifications](https://developers.google.com/workspace/gmail/api/auth/scopes).
