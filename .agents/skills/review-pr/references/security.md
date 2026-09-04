# Security review

Apply only the sections relevant to the changed capability. Trace a real path from
attacker-controlled input or authority to an asset, disclosure, side effect, or
resource cost; do not report attack names without a reachable sink.

## Threat sketch

Identify:

- the actor: anonymous/public user, workspace role, integration, automation,
  background task, or explicit system principal;
- what the actor controls: ids, content, URLs, files, expressions, filters,
  quantities, timing, and ordering;
- whose authority and credentials perform the effect;
- data and effects read, written, deleted, sent, rendered, cached, logged, or
  broadcast;
- the maximum tenant/resource blast radius, cost, and available recovery.

Trace every applicable entry point: API, websocket, public/restricted view, handler,
`ActionType`, task, automation, integration, import/export, duplicate, and registry
hook. Ask separately who requests, who authorizes, who acts, who receives the result,
and who bears the cost.

## Authority, isolation, and misuse

- Authorize the actual effect with the correct `OperationType` and authoritative
  resource context before resolving secrets, constructing expensive work, making a
  network call, enqueueing, or mutating. A denial has no downstream side effects.
- Derive workspace and parent ids from the resolved object. A client cannot combine
  an authorized child with another tenant's parent. Identifiers locate resources;
  they do not grant authority.
- Enforce the boundary at the layer every ordinary, bulk, import, background,
  websocket, and internal path crosses. `None` never means unrestricted; actorless
  work requires an explicit, deliberately scoped system authority.
- Prevent confused-deputy behavior. A lower-role user cannot use another user's
  integration, token, assistant, automation, or privileged service to perform an
  action or obtain a response they could not access directly.
- Server-owned fields such as actor, tenant, role, ownership, verification, and
  state are not writable through mass assignment.
- Public and restricted views apply their visibility to single reads, lists, search,
  aggregates, exports, and realtime. They do not reveal hidden fields/formulas,
  full-access user ids, or protected object existence through different errors.
- Treat capabilities compositionally: can a legitimate feature become mass
  read/write/delete, arbitrary outbound requests, recursive automation, bulk
  notification, credential use, or unbounded paid work? Bound and attribute it to
  the actor/resource that bears the damage.
- Wide or irreversible operations need scope, audit, idempotency, cancellation,
  undo, or recovery proportional to their blast radius. UI hiding is never the
  enforcement boundary.

## Injection and unsafe interpretation

Keep attacker data structured until the sink; escaping for one interpreter does not
make it safe for another.

- **SQL injection:** keep values in ORM parameters or `cursor.execute(..., params)`.
  Allowlist dynamic table/column/schema/order fragments and wrap identifiers with the
  repository's psycopg identifier helpers. Trace every fragment in raw SQL,
  `RawSQL`, `.extra()`, formula/filter compilation, and security suppressions.
- **XSS and unsafe URLs:** inspect `v-html`, `innerHTML`, markdown/rich-text rendering,
  editor serialization, `href`, `src`, CSS URLs, redirects, `window.open`, email, and
  public Builder pages. Escape text at the final sink; sanitize intended rich content
  after parsing; allowlist URL schemes and encode components separately. Test stored
  payloads after save/reload and realtime/import/duplicate flows.
- **Commands, paths, and archives:** pass argument vectors without a shell; allowlist
  any executable/grammar. Resolve storage paths beneath the intended root and reject
  traversal, absolute paths, alternate separators, symlink escapes, and overwrite.
  Workspace imports extract only signed-manifest members.
- **Templates, formulas, and expressions:** use the owning parser/AST and an
  allowlisted context. Do not use regex rewriting, general evaluation, or template
  engines where a restricted language is promised. Treat LLM and integration output
  as untrusted input and independently authorize every tool effect.
- Consider unsafe deserialization, spreadsheet/formula injection, regex or parser
  denial of service, and decompression bombs when the changed path reaches those
  interpreters.

## Server-side requests and files

- Every user-influenced server fetch uses advocate, including redirects, discovery,
  previews, webhooks, syncs, integrations, and AI providers. Validate scheme, port,
  every redirect, loopback/link-local/CGNAT, mapped and transition IPv6 forms, and the
  host's own addresses; `ip.is_private` alone is insufficient.
- Resolve once and connect to that validated result. Bound connection/read/statement
  time, redirects, retries, streamed and decompressed bytes, and cleanup. Check the
  enterprise proxy impact before changing an existing flow.
- Rich-text files refer to an existing accessible `UserFile`; client filenames,
  extensions, and MIME types are not trusted. Serve active content through the
  established neutralization and content-disposition path.
- Never return raw upstream bodies, headers, private addresses, diagnostic URLs, or
  provider internals to a lower-authority caller.

## Secrets and security-relevant disclosure

Trace sensitive or operational data through API responses, websocket events, logs,
errors, traces, metrics, task arguments, caches, exports, snapshots, templates,
data providers, audit entries, and AI prompts—not only the primary serializer.

- Passwords, hashes, tokens, cookies, auth headers, OAuth codes, reset links, signed
  URLs, DSNs, private keys, and integration credentials are write-only and omitted or
  irreversibly masked. Service types declare `sensitive_fields`.
- Redact before serialization, queueing, caching, tracing, or logging. UI masking does
  not protect browser state or the underlying response.
- Avoid `logger.exception` in frames containing external requests or user payloads:
  Loguru diagnostics can expose locals, headers, URLs, and secrets. Log safe ids and
  the exception class; neutralize control characters and redact query strings.
- Errors support recovery without revealing tenant membership, object existence,
  authentication configuration, internal topology, filesystem paths, SQL fragments,
  stack frames, or upstream credentials.
- Cache keys, broadcasts, notifications, and search results preserve tenant and
  visibility scope. Permission-filtered data is never reused under a broader key.

## Resource exhaustion and races

- For inbound HTTP, determine which parser reads the body, whether the proxy, WSGI/
  ASGI server, framework, or application buffers it, and which layer enforces the
  limit. Cover missing or dishonest `Content-Length`, chunked bodies, compressed
  input, and anonymous endpoints; reject before materializing the oversized body
  with the intended HTTP status and API error shape.
- Keep request-data limits separate from file/storage limits unless they protect the
  same resource and threat boundary. Verify both allowed and rejected behavior on a
  real endpoint and confirm the default deployment proxy does not silently remove or
  replace the application guarantee.
- Bound attacker-selected length, cardinality, recursion/dependency depth, regex or
  expression complexity, file/decompressed size, pagination, task/broadcast fan-out,
  external latency, retries, and concurrency. Rate limits cannot be bypassed by
  switching equivalent actor/provider identities.
- Validation, authorization, accounting, execution, and response use one coherent
  resource/version snapshot. Lock, version, compare-and-swap, or deliberately recheck
  when concurrent change alters the decision.
- Cleanup verifies the exact resource generation it acquired. A stale timeout,
  cancellation, or task completion cannot delete or overwrite its replacement.

## Adversarial verification

Use a few tests that prove boundaries:

- allowed actor, lower role, valid object id from another workspace, public/anonymous
  actor when applicable, and actorless/background path;
- malicious input through the real persistence and sink for SQL, HTML, URL, path,
  template/expression, file, or command handling;
- a seeded canary secret captured across responses, events, exports, logs, traces,
  tasks, caches, and prompts;
- limits at and just above the boundary, including alternate encodings, redirects,
  compressed content, and concurrent/retry paths;
- guarded requests asserting no forbidden mutation, external call, task, broadcast,
  or disclosure occurred.

Use controlled barriers for races rather than sleeps. A mock that bypasses the real
parser, client, or guard is not security evidence.
