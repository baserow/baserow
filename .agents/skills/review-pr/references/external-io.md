# External I/O and background work review

Use this reference for HTTP integrations, webhooks, data syncs, remote imports,
AI providers, SMTP, SSO, object storage, user-configured databases, Celery, Redis,
locks, scheduling, and asynchronous cleanup. Also load the security reference when
a user influences the destination, credentials, request, or response.

## Bound the complete operation

For one user action or scheduled run, calculate destinations, calls and pages per
destination, rows/recipients/files/events per call, bytes before and after
decompression, whole-operation time, tasks, and simultaneous connections. Multiply
by plausible concurrent users or workspaces and compare with provider quotas,
worker capacity, queue growth, and memory per worker.

- Bound DNS, connect, TLS/authentication, commands, redirects, headers, body
  streaming, provider pagination, retries, and cleanup. An inactivity timeout is not
  necessarily a wall-clock deadline.
- Stream and stop before a post-decompression ceiling is exceeded. Bound requests,
  attachments, parsed content, persisted raw results, page count, record count, and
  cursors that fail to advance.
- Reuse a bounded client/session for the operation and close every response, socket,
  cursor, session, and temporary file on success, failure, timeout, and cancellation.
- Do not hold a database transaction or row lock during remote I/O. Persist the job
  or checkpoint first, then perform the call.

## Retry, idempotency, and ownership

- Retry only documented transient failures, with capped attempts, backoff/jitter,
  and one total deadline. Ensure client, orchestration, and Celery retries do not
  multiply into a storm.
- Side-effecting calls require an idempotency/delivery identity or a reconciliation
  rule. Define partial-success behavior so retry neither duplicates nor skips work.
- Rate and concurrency limits are atomic and scoped to the resource bearing the
  cost. Check fairness between tenants and recovery after worker loss.
- A singleton or lock has a lease covering the full operation or refreshes it while
  working. Cleanup verifies ownership/generation so a stale worker cannot clear or
  overwrite a replacement.
- Async work carries the initiating actor, tenant/resource identity, and effective
  configuration snapshot. A later edit or permission change must not silently make
  preflight, execution, and the reported result disagree.

## Configuration and protocol contracts

- Verify timeout, redirect, signature, pagination, proxy, and retry semantics against
  the library/provider's public contract and, when necessary, its source. Do not
  mutate private SDK internals.
- Trace each selectable provider and setting from UI/API through deployment config
  to the exact executing process. Give a container or task only the credentials it
  needs; do not pass unrelated LLM, database, or integration secrets.
- Namespace discovery and fallback state by project/tenant/provider so a local tool
  cannot attach to an unrelated service accidentally.
- Keep requested configuration separate from effective configuration. Persist and
  display what actually ran, including version, prompt/model/provider, population,
  and partial/completion status where those affect interpretation.

## Degraded peers and observability

Exercise applicable real-client behavior: connect-without-response, slow-drip body,
compressed expansion, redirect/pagination ceilings, disconnect after partial work,
`429`, transient `5xx`, permanent `4xx`, malformed content, duplicate delivery, and
concurrent runs. Assert attempt/call count, stopping point, resource closure,
checkpoint state, and absence of later calls after failure.

Celery eager tests do not model queued duplicates, broker payloads, backlog, or real
concurrency; patch `.delay` for enqueue behavior and call out what remains untested.

Log bounded operational metadata such as safe object id, attempt, outcome class,
duration, byte/item count, and the limit that stopped work. Do not log per-item noise,
raw headers/bodies, credentials, signed URLs, query strings, provider-echoed secrets,
or frame locals.
