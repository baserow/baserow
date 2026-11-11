# MCP OAuth sign-in for self-hosted Baserow

With `BASEROW_MCP_OAUTH_ENABLED=true`, MCP clients such as Claude, ChatGPT, Cursor and
VS Code connect to `<PUBLIC_BACKEND_URL>/mcp` and sign the user in with OAuth instead
of a pasted endpoint key. Setup steps for each client are in the
[baserow-mcp README](https://github.com/baserow/baserow-mcp). A few things to check on
a self-hosted install:

* **Public HTTPS URL.** Apps like claude.ai, Claude Desktop and ChatGPT reach Baserow from
  the internet, so `PUBLIC_BACKEND_URL` (or `BASEROW_PUBLIC_URL`) must be the public HTTPS
  URL. Otherwise the app fails early, claude.ai for example only says "Couldn't
  register". CLI apps such as Claude Code on the same machine also work with
  `localhost`.
* **Routing.** Besides `/api/` and `/ws/`, the reverse proxy must send `/mcp`,
  `/oauth/`, `/.well-known/oauth-authorization-server` and
  `/.well-known/oauth-protected-resource` to the backend. `/mcp` must reach the ASGI
  backend. The [Caddyfile](https://github.com/baserow/baserow/blob/master/Caddyfile),
  the [Nginx](install-behind-nginx.md), [Apache](install-behind-apache.md) and
  [K8S](install-with-k8s.md) guides already do this. To submit your own ChatGPT app
  to OpenAI, also send `/.well-known/openai-apps-challenge` to the backend and set
  `BASEROW_MCP_OPENAI_APPS_CHALLENGE`. Only the Caddyfile routes it already.
* **Outbound HTTPS.** Apps that identify themselves with a client metadata document
  (CIMD), like Claude, ChatGPT and VS Code, make the backend fetch that document over
  HTTPS. The fetch connects directly and ignores `HTTPS_PROXY`. Without direct outbound
  HTTPS, set `BASEROW_MCP_OAUTH_CIMD_ENABLED=false`; those apps then register
  themselves instead (DCR).
* **Client IP for rate limits.** The OAuth rate limits count per client IP, taken from
  the first `X-Forwarded-For` entry. The proxy in front of Baserow must replace that
  header rather than append to what the client sent, or a client can pick its own IP.
  Behind a proxy that doesn't set it at all, every client shares one limit.
* **Turning it off.** Setting `BASEROW_MCP_OAUTH_ENABLED=false` pauses the connected
  apps, it doesn't revoke them. Their grants and tokens are kept and work again when
  the flag is turned back on. Users can disconnect apps in *My settings → MCP server*.
