# Integrations that connect an account

Some integrations hold one person's account at another service: a builder signs in
with that service, and the integration's actions then act as that account. They all
work the same way, whatever the provider. Each provider's own setup page explains how
to register Baserow with it, and links here for what they share.

## Registering Baserow with a provider

Baserow signs in through an OAuth app registered with the provider: the authorization
code flow with PKCE, as a confidential client, then refresh tokens. By default one app
is registered for the whole installation and builders never see it. Until an admin
registers it, accounts of that provider can't be connected, and the integration form
says so.

Every provider sends the person back to the same kind of page. Register this redirect
URI with the provider's app, for the provider's integration type:

```
<PUBLIC_WEB_FRONTEND_URL>/integrations/<integration type>/oauth-callback
```

For example `https://baserow.example.com/integrations/microsoft/oauth-callback`. A
builder sees the exact value in the integration form while the app isn't set up.

An app's client secret usually expires. When it does, every account connected through
it stops working until you set a new secret, so note the date and plan the rotation.

## How connecting works

- Builders connect an account from the integration form, in a popup. Signing in while
  creating the integration creates it; signing in again later reconnects it.
- Baserow only asks for what the actions need. The first sign-in asks for the account's
  identity and a refresh token, plus what the action it's made for needs. When another
  action needs more, the builder grants it from that action's settings.
- A sign-in can only be finished by the person who started it, within ten minutes. One
  person can start at most 20 sign-ins a minute and 200 an hour.
- If the provider's organisation only lets admins approve apps, the form shows a link
  to send to the organisation's admin, when the provider has one.

## What builders should know

- Actions act as the account that signed in, whoever triggers them: a visitor of a
  published application, or an automation run.
- Disconnecting makes Baserow forget the tokens. Published applications and workflows
  keep their own copy until they're published again.
- A duplicate keeps the connection while whoever connected it is still a member of
  the workspace. Exports, templates and snapshots never contain it: an imported or
  restored integration must be connected again.
- When the person who connected an account leaves the workspace, or their Baserow
  account is deleted, Baserow forgets the tokens, in published copies and the trash
  too. The account stays shown, so the next editor knows whom to sign in as.
- To remove Baserow's access entirely, people revoke the app in their account at the
  provider.

## Adding a provider

For developers. A provider is an integration type built on the shared base in
`backend/src/baserow/contrib/integrations/oauth_account/` and
`web-frontend/modules/integrations/oauthAccount/`:

1. A model that extends `OAuthAccountIntegrationMixin` and `Integration`, declaring its
   own `access_token` and `refresh_token` as `EncryptedTextField`s with a context of
   its own. Fields of its own that a sign-in sets go in `extra_connection_fields`.
2. An `OAuthProvider` subclass: its endpoints, how it tells who signed in
   (`identify`), its base scopes and how its errors read. Its behaviour flags,
   `allow_account_switch`, `keep_connection_in_duplicates` and
   `keep_connection_in_published_copies`, are shared product decisions: change them
   for every provider at once. To let an integration bring its own OAuth client, return
   it from `get_client`.
3. An integration type that extends `OAuthAccountIntegrationTypeMixin` and sets
   `provider`. The sign-in endpoints, under `/api/integrations/oauth/<type>/`, come
   with it.
4. Service types that extend `OAuthAccountServiceTypeMixin`, with `required_scopes` and
   `permission_description`. `request_as_account` sends a request as the account and
   turns the provider's answers into dispatch errors; build paths from formulas with
   `quote_path_segments`. Services serialize their `required_scopes`, so the
   frontend never repeats them.
5. On the frontend, a type that extends `OAuthAccountIntegrationType` with its
   `providerName` and `image`. Its form is `OAuthAccountForm`, or a form of its own
   that wraps it and adds fields in its `extras` slot. To offer "Grant access" in an
   action's form, use the type's `getMissingScopes(integration, service)`.
6. A setup page in `docs/installation/` that links to this one.
