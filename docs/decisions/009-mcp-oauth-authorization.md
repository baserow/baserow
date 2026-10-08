# ADR 009: Authenticate MCP clients with OAuth

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-07                                     |
| Issue        | https://github.com/baserow/baserow/issues/6260 |
| Author       | Al Amin (@alamin-br)                           |
| Contributors | Davide (@silvestrid)                           |

## Summary

AI apps (MCP clients) connect to Baserow with a secret key in the URL. This ADR moves them
to the OAuth sign-in the
[MCP spec](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
defines: Baserow runs its own OAuth server, and users choose what each app can access.

## Context

Each key gives an app its owner's full permissions in one workspace, with no way to limit
it to some tools.

This has to change because:

- The main AI apps expect OAuth. Claude's connector directory requires it for anything
  that acts on a user's account, ChatGPT can't send API keys at all, and Claude can send
  them only in a limited beta.
- A key in a URL leaks into logs and browser history.

The goal is sign-in that works with the major AI apps, on SaaS and self-hosted instances,
without an external identity provider or per-app setup.

## Decision

1. Baserow runs its own OAuth server in core, built on
   [django-oauth-toolkit](https://django-oauth-toolkit.readthedocs.io/).
2. The MCP spec prefers CIMD and has deprecated DCR, but Cursor, Gemini CLI and other
   major apps still only support DCR, so Baserow accepts both.
3. Every app connects to one shared URL that carries no credentials. It uses Streamable
   HTTP, which replaces the deprecated SSE transport.
4. Sign-in uses the normal Baserow login, so SSO and 2FA apply. A consent page shows which
   app is asking, warns when its identity can't be verified, and lets the user pick which
   workspaces and tools it gets.
5. Each approved app gets a connection that acts only as that user, within the chosen
   workspaces and tools. Every call checks again that the user is still active and still a
   member of the workspace. Tools the user didn't pick are blocked, not just hidden.
6. Users stay signed in until they disconnect the app, which takes effect immediately, or
   until it goes unused for 30 days. Connecting and disconnecting are recorded in the
   audit log.
7. Scripts and apps that can't use OAuth keep their keys, sent in a request header instead
   of the URL, with the tools they have today. URLs with a key in them keep working until
   almost nobody uses them.
8. Baserow fetches an app's metadata with the same protections as its other outbound
   requests, and admins can restrict which hosts it trusts. The registration and token
   endpoints are open to anyone, so they're rate-limited. The consent page can't be
   approved from another site or from inside a frame.

## Options considered

| Option                                     | Why not                                                                                                          |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Keep the key in the URL                    | It leaks, can't be limited, and ChatGPT and the app directories don't accept it.                                 |
| API keys in the header only                | ChatGPT can't send them, and users get no consent step. Kept for scripts.                                        |
| External identity provider (Auth0, WorkOS) | Every self-hosted instance would need its own account with the provider, and core would depend on a third party. |
| CIMD only                                  | Cursor, Gemini CLI and other major apps can't sign in.                                                           |
| DCR only                                   | Deprecated by the spec, and needs an open registration endpoint.                                                 |
| Client IDs set up by an admin              | Users would copy a client ID into each app, and some apps have nowhere to put it.                                |

## Consequences

- Once the old key URLs are gone, no secret travels in a URL.
- Every install gets a new dependency.
- Cloud apps such as claude.ai and ChatGPT can only reach instances on the public internet
  over HTTPS. Apps on the user's own machine, such as Claude Code, also work on a private
  network.
- Instances without outbound internet can't fetch app metadata, so only apps that use DCR
  can sign in.

## Revisit triggers

- The MCP spec changes how apps sign in.
- Once the major apps support CIMD, turn DCR off by default.
- Once almost nobody uses the old key URLs, remove them.
