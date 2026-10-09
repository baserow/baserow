# ADR 009: Authorize MCP clients with OAuth

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-07                                     |
| Issue        | https://github.com/baserow/baserow/issues/6260 |
| Author       | Al Amin (@alamin-br)                           |
| Contributors | Davide Silvestri (@silvestrid)                 |

## Summary

AI apps (MCP clients) connect to Baserow with a secret key in the URL. The key leaks,
can't be limited to some tools, and ChatGPT and Claude's connector directory don't accept
it. Baserow will run its own OAuth server as the
[MCP spec](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
defines, so users sign in from the app and choose which workspaces and tools it can use.

## Context

Today a user creates an MCP endpoint for one workspace in their settings and pastes its
URL into the app. The URL holds a secret key that gives the app its owner's full
permissions in that workspace, with no way to limit it to some tools. The endpoint uses
SSE, a transport the MCP spec has deprecated.

This has to change because:

- The main AI apps expect OAuth. Claude's connector directory requires it for anything
  that acts on a user's account, ChatGPT can't send API keys at all, and Claude can send
  them only in a limited beta.
- A key in a URL leaks into logs and browser history.

The goal is sign-in that works with the major AI apps, on SaaS and self-hosted instances,
without an external identity provider or per-app setup.

In scope: how apps identify themselves, sign users in and get limited access, and what
happens to existing endpoint keys. Out of scope: OAuth for the REST API or other
integrations, which tools exist, and Baserow connecting to other MCP servers.

| Term            | Meaning                                                                                                |
| --------------- | ------------------------------------------------------------------------------------------------------ |
| App             | An AI app that uses Baserow's tools over MCP, such as Claude, ChatGPT or Cursor.                       |
| Endpoint key    | The secret in today's MCP endpoint URL. Not a database token.                                          |
| CIMD            | Client ID Metadata Document: the app's ID is a URL to a document describing it, which Baserow fetches. |
| DCR             | Dynamic Client Registration: the app registers itself with Baserow on first use and gets an ID back.   |
| Connection      | One app approved by one user, with the workspaces and tools they picked. Disconnecting ends it.        |
| Streamable HTTP | The MCP transport that replaces SSE.                                                                   |

## Decision

### 1. Baserow is its own OAuth server

Baserow runs its own OAuth server in core, built on
[django-oauth-toolkit](https://django-oauth-toolkit.readthedocs.io/), so neither SaaS nor
self-hosted instances need an external identity provider.

### 2. Apps identify themselves with CIMD or DCR

The MCP spec prefers CIMD and has deprecated DCR, but Cursor, Gemini CLI and other major
apps still only support DCR, so Baserow accepts both.

### 3. One endpoint, no credentials in the URL

Every app connects to one shared URL that carries no credentials. It uses Streamable HTTP,
which replaces the deprecated SSE transport.

### 4. Sign-in and consent

Sign-in uses the normal Baserow login, so SSO and 2FA apply. A consent page shows which
app is asking, warns when its identity can't be verified, and lets the user pick which
workspaces and tools it gets.

### 5. What a connection can do

A connection acts only as its user, within the chosen workspaces and tools. Every call
checks again that the user is still active and still a member of the workspace. Tools the
user didn't pick are blocked, not just hidden.

### 6. How long a connection lasts

A connection lasts until the user disconnects the app, which takes effect immediately, or
until it goes unused for 30 days. Connecting and disconnecting are recorded in the audit
log.

### 7. Endpoint keys for scripts

Scripts and apps that can't use OAuth keep their endpoint keys, sent in a request header
instead of the URL, with the tools they have today. URLs with a key in them keep working
until almost nobody uses them.

### 8. Protecting the public endpoints

- Baserow fetches an app's metadata with the same protections as its other outbound
  requests, and admins can restrict which hosts it trusts.
- The registration and token endpoints are open to anyone, so they're rate-limited.
- The consent page can't be approved from another site or from inside a frame.

## Options considered

| Option                                         | Why not                                                                                                          |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Keep the key in the URL                        | It leaks, can't be limited, and ChatGPT and the app directories don't accept it.                                 |
| API keys in the header only                    | ChatGPT can't send them, and users get no consent step. Kept for scripts.                                        |
| External identity provider (Auth0, WorkOS)     | Every self-hosted instance would need its own account with the provider, and core would depend on a third party. |
| Separate OAuth service (Keycloak, Ory Hydra)   | Every install would run and secure another service in its stack.                                                 |
| Authlib instead of django-oauth-toolkit        | No MCP authorization support, while django-oauth-toolkit added it in 3.4.0.                                      |
| CIMD only                                      | Cursor, Gemini CLI and other major apps can't sign in.                                                           |
| DCR only                                       | Deprecated by the spec, and needs an open registration endpoint.                                                 |
| Client IDs set up by an admin                  | Users would copy a client ID into each app, and some apps have nowhere to put it.                                |

## Consequences

- Once the old key URLs are gone, no secret travels in a URL.
- Until then, MCP has three ways to sign in (OAuth, a key in a header, a key in the URL),
  and all three need maintaining and testing.
- Baserow runs a security-critical service in core, on a new dependency, and has to keep
  up with the spec's sign-in rules as they change. Which apps can connect also depends on
  how fast that dependency keeps up.
- Cloud apps such as claude.ai and ChatGPT can only reach instances on the public internet
  over HTTPS. Apps on the user's own machine, such as Claude Code, also work on a private
  network.
- Instances without outbound internet can't fetch app metadata, so only apps that use DCR
  can sign in.
- Follow-up work: the consent page, a page to list and disconnect connections, accepting
  existing keys in a header, measuring how many requests still use key URLs and removing
  them once almost none do, and self-hosting docs for public HTTPS and outbound access.

## Revisit triggers

- The MCP spec moves away from OAuth or changes how apps sign in.
- django-oauth-toolkit stops supporting the main AI apps we want to support.
