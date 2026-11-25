# Microsoft integration setup

Builders connect a Microsoft account to Baserow by signing in with Microsoft. The
sign-in goes through one Microsoft Entra app registered for the whole installation:
builders never see it, and they don't need one of their own. Until an admin registers
it, Microsoft accounts can't be connected.

Baserow Cloud has its own app. These steps are for self-hosted installations.

## 1. Register the app

1. Sign in to the [Microsoft Entra admin center](https://entra.microsoft.com) and go to
   **Identity > Applications > App registrations > New registration**.
2. Enter a name people will recognise on the Microsoft consent screen, for example
   "Baserow".
3. Under **Supported account types**, choose who can sign in:
   - **Accounts in any organizational directory and personal Microsoft accounts** for
     work, school and personal accounts. Keep `BASEROW_INTEGRATIONS_MICROSOFT_TENANT` at
     its default, `common`.
   - **Accounts in this organizational directory only** to limit it to your
     organisation. Set `BASEROW_INTEGRATIONS_MICROSOFT_TENANT` to your tenant ID.
4. Under **Redirect URI**, pick **Web** and enter
   `<PUBLIC_WEB_FRONTEND_URL>/integrations/microsoft/oauth-callback`, e.g.
   `https://baserow.example.com/integrations/microsoft/oauth-callback`. A builder sees
   the exact value in the Microsoft integration form while the app isn't set up.
5. Click **Register**, then copy the **Application (client) ID**.

## 2. Create a client secret

1. In the app, open **Certificates & secrets > Client secrets > New client secret**.
2. Choose an expiry and copy the secret's **Value**.

Microsoft secrets expire after at most 24 months. When the secret expires, every
connected Microsoft account stops working until you set a new one, so note the date and
plan the rotation.

## 3. Add the permissions

Open **API permissions > Add a permission > Microsoft Graph > Delegated permissions**
and add `openid`, `profile`, `email`, `offline_access` and `User.Read`.

Baserow asks for further permissions only when an action needs them, the first time a
builder uses that action. Add those here too, so they appear on the consent screen your
users and admins review:

| Action                                    | Delegated permissions                                                                                      |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Send Teams message (Advanced, Enterprise) | `ChannelMessage.Send`, `ChatMessage.Send`, `Team.ReadBasic.All`, `Channel.ReadBasic.All`, `Chat.ReadBasic` |

The Teams action only works with work or school accounts.

None of these permissions need admin consent by default, but your organisation may
only let admins approve apps. Then either click **Grant admin consent** for your
organisation here, or have builders send their admin the approval link Baserow shows
when their sign-in is refused.

## 4. Configure Baserow

Set these environment variables on the backend and restart it:

```bash
BASEROW_INTEGRATIONS_MICROSOFT_CLIENT_ID=<application (client) id>
BASEROW_INTEGRATIONS_MICROSOFT_CLIENT_SECRET=<client secret value>
# Only for a single-tenant app:
BASEROW_INTEGRATIONS_MICROSOFT_TENANT=<tenant id>
```

See [Configuration](./configuration.md) for the full list, including the hosts used by
national clouds.

## What builders should know

Microsoft integrations work like every integration that connects an account: who they
act as, reconnecting and disconnecting, what copies and exports keep. See
[Integrations that connect an account](./oauth-account-integrations.md).

- To remove Baserow's access entirely, people remove the app from
  [My Apps](https://myapps.microsoft.com) for a work or school account, or from
  [account.live.com/consent](https://account.live.com/consent/Manage) for a personal
  account.
