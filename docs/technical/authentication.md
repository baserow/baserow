# Authentication and sessions

Authentication answers "who is making this request?". Authorization answers
"can they do this?" and is covered in [Permissions](permissions-guide.md).

Baserow has four request contexts:

| Context | Used by | Header / mechanism |
|---|---|---|
| Baserow user JWT | Web app, SDK clients | `Authorization: JWT <token>` |
| Database API token | External database API integrations | `Authorization: Token <key>` |
| User source JWT | Published builder-app end users | `UserSourceAuthorization` |
| Anonymous | Login, signup, public forms/views/pages | `AllowAny` plus endpoint checks |

## DRF Wiring

Global DRF authentication tries user-source JWT first, then normal Baserow user
JWT. Database API tokens are added per view because only selected database
endpoints accept them.

The default permission class is authenticated. Public endpoints opt into
`AllowAny` and must do their own access checks, such as public-view password
validation.

## Baserow User JWT

Normal authenticated requests use simplejwt with Baserow's custom
`JSONWebTokenAuthentication`.

Important rules:

- The auth header is `Authorization: JWT <token>`, not `Bearer`.
- Access tokens are short-lived; refresh tokens keep browser sessions alive.
- Use `BASEROW_JWT_SIGNING_KEY` so JWT rotation does not also rotate every
  Django-signed artifact tied to `SECRET_KEY`.
- Cross-cutting user-state checks belong in
  `JSONWebTokenAuthentication`; per-operation checks belong in services or
  actions through permissions.

Login returns access token, refresh token, `user_session`, and user metadata.
The frontend stores tokens in cookies and refreshes automatically through the
axios auth-refresh plugin.

`ClientSessionId` is separate from auth. It is untrusted per-tab context used
for undo stacks.

## Database API Tokens

Database API tokens are long-lived, workspace-scoped bearer strings for external
clients that call database row endpoints.

Key points:

- The key is shown once at creation time.
- Token auth is wired on endpoints that explicitly support it.
- Token permissions are checked by the database token permission manager.
- If a REST endpoint is token-accessible, update
  `web-frontend/modules/database/pages/APIDocsDatabase.vue`; that page is not
  generated from OpenAPI.

## User Source Tokens

Published builder apps can have their own end users. Those users are not
Baserow users and use a separate JWT header: `UserSourceAuthorization`.

When handling builder dispatch/runtime endpoints, use
`request.user_source_user`; do not assume `request.user` is the actor.

## Anonymous Access

Anonymous endpoints include:

- Login, signup, password reset, email verification.
- Public form submissions.
- Public view reads.
- Published builder app dispatch.

`AllowAny` only disables authentication requirement. The view still owns public
access checks, password tokens, throttling assumptions, and anti-abuse behavior.

## SSO, 2FA, and Captcha

- SSO/SAML/OIDC/OAuth are enterprise auth-provider flows. On success they issue
  a normal Baserow JWT.
- 2FA uses a short-lived pre-auth token after password login; full JWT issuance
  happens only after successful second-factor verification.
- Captcha providers gate signup/password-reset style flows when configured.

See [SSO / SAML](../development/sso-saml.md) for setup details.

## Sessions and Logout

JWT sessions are mostly client-side. Logout clears cookies. Server-driven
invalidation uses refresh-token blacklist state; already-issued access tokens
remain valid until expiry.

Use frontend `forceLogoff` when server state requires clearing local auth state
immediately.

## Adding an Endpoint

1. **JWT-only**: default behavior; do not override auth classes.
2. **JWT or anonymous**: set `permission_classes = [AllowAny]` and add explicit
   access checks.
3. **Database token support**: add token authentication to the view while keeping
   normal JWT support, and update the custom token API docs page.
4. **Builder public runtime**: use the user-source auth context and dispatch
   infrastructure.

## Configuration

See [Configuration](../installation/configuration.md) for the full env-var
reference. Auth-related settings include JWT signing/lifetimes, concurrent-user
request throttling, and IP throttling.

## Related

- [Permissions](permissions-guide.md).
- [Frontend architecture](../patterns/frontend-architecture.md).
- [Endpoints](../patterns/endpoints.md).
- [SSO / SAML](../development/sso-saml.md).
