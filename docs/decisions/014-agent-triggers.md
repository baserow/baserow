# ADR 014: Start agent runs from core trigger services

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-11-09                                     |
| Issue        | https://github.com/baserow/baserow/issues/6259 |
| Author       | Davide Silvestri (@silvestrid)                 |
| Contributors | Bram Wiepjes (@bram2w)                         |

## Summary

Agents only answered when a person wrote to them. We let an agent own triggers built
on the trigger services Automation workflows already start from, and open a
conversation whenever one fires. Three decisions carry this: trigger service types
notify every registered listener and expose `arm()` so a service can go live without
Automation's publish step; a trigger-started conversation is shared, modelled as a
conversation with no owner; and an unattended run pauses on held calls until an
editor decides them, like any other run.

## Context

Trigger service types (`periodic`, `http_trigger`, `email_trigger`, the row and field
signal types) produce events and find the `Service` rows that should receive them.
Until now each type held exactly one callback, set by the Automation trigger node type
when it registered; a second consumer replaced it. Making a service live was done
inline when a workflow was published: the import code set `next_run_at` for periodic
services and `is_public` for HTTP and email services.

Agent conversations had a non-null owner. The owner was the permission subject every
reply ran as, the only reader, the realtime recipient and the only possible approver.
Nothing expected a reply to start without a person, except the core chat-run engine,
which already accepts runs with no user.

Agent Builder is behind `FF_AGENT_BUILDER` and has no production users, so no
mixed-version compatibility is needed for these changes.

| Term                 | Meaning                                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Trigger              | An `AgentTrigger` row: an agent-owned wrapper of one trigger service, with an enabled switch and a message formula. |
| Trigger service      | The `Service` row (periodic, HTTP, email, rows) that produces events; owned by exactly one consumer.                |
| Event payload        | The dict a service type produces per event; exposed to the trigger message as the `trigger` data provider.          |
| Listener             | A callable a consumer registers to receive `(services, event_payload, user, isolate_failures)`.                     |
| Armed                | A trigger service that receives real events now: periodic `next_run_at` set, HTTP/email `is_public`.                |
| Shared conversation  | A conversation with `owner_user IS NULL`; readable by everyone with `read_conversations` on the agent.              |
| Private conversation | A conversation started by a person; visible to that person only. Unchanged.                                         |
| Run identity         | The subject the agent's tools act as. Never a conversation owner, never an author.                                  |
| Ask-first tool       | An allowed tool whose calls pause the reply until a person approves them.                                           |

In scope: how events reach consumers, how a service goes live, who owns and sees
trigger-started conversations, and what an unattended run may do. Out of scope: which
trigger types the picker offers (a constant, widened per release), rate limits and
auto-disable, continuation of shared conversations, the agent-level pause and "Run
once".

## Decision

### 1. Trigger fan-out and arming live in core

`TriggerServiceTypeMixin` keeps a list of listeners. `start_listening(cb)` appends and
calls `connect()` when the list was empty; `stop_listening(cb)` removes and calls
`disconnect()` when it becomes empty; `on_event` materialises the services once and
returns every listener's results concatenated. `ServiceTypeRegistry.add_trigger_listener(cb)`
subscribes a consumer to every trigger type, including types registered later, so the
order of `INSTALLED_APPS` and plugins does not matter.

`arm(service)` is the one way to make a service receive real events. Periodic sets
`next_run_at`; HTTP and email set `is_public`. Automation's publish calls the same hook
instead of its three inline branches; agents call it when a trigger is created, its
service values change, or it is enabled. There is no `disarm`: a disabled trigger keeps
its schedule and is skipped at dispatch, a trashed one leaves the due set with its
service.

`ServiceMisconfigured` is a core exception; Automation's error subclasses it, so
the periodic service type no longer imports an Automation exception at module level.

A consumer holds the foreign key to its service (`AgentTrigger.service`, as automation
nodes, data sources and button actions do). `Service` knows no owner.

### 2. A trigger-started conversation is shared: it has no owner

`AgentConversation.owner_user` becomes nullable and a `trigger` foreign key (set to
null when the trigger is deleted) records what started it. Shared means exactly
`owner_user IS NULL`. Shared conversations are visible to everyone with
`read_conversations` on the agent; private ones stay visible to their owner only.

Renaming, trashing, restoring and stopping a shared conversation additionally require
`application.update`. Following its runs live requires `read_conversations`. Sending a
message in one is refused in this release; continuation by editors is a later change.
Its held calls are decided like a private one's, by anyone who may send the agent
messages, so editors approve or reject a call and only builders, who may update the
configuration, also always allow its tool. Realtime updates go to the users permitted
to read the agent's conversations instead of one owner, and its pending count to
everyone who may decide it.

Viewers only read conversations. Renaming, trashing and restoring any conversation,
a private one included, needs the editor role, the lowest role that may create one.

The opening message, with role `trigger`, holds the resolved trigger message (a runtime
formula over the event payload, or the payload as JSON when it resolves to blank text).
It is the only record of what the model received; the title derives from it, and no raw
payload column exists. Triggers that arrive through duplicate, snapshot restore or
template install are always disabled.

### 3. Trigger runs have no sender

A trigger run's tools act as the agent's run identity, as in any run, but the run has
no sender: `created_by` names the person who sent the message, and a trigger isn't
one. So `created_by=None`: the per-user run cap does not apply, the workspace cap does, and a cap hit records a failed reply with the code
`chat_run_limit_reached` instead of disappearing. Ask-first tools are offered as in any
run: a held call pauses the reply until an editor decides it, and the resumed run
has no sender either. A waiting reply counts as going, so the trigger's overlap rule
skips or queues the firings that come meanwhile instead of piling up waiting
conversations. Their tools read dates in the trigger's
timezone (the service's own, or UTC when its type has none), so a daily digest's
"today" is the day the builder scheduled it for.

The dispatcher resolves the payload of every matched trigger before filtering, so a
disabled trigger still advances its schedule and never fires a backlog when enabled
again. It resolves each enabled trigger's message during the event, then starts the
conversation in a task once the event's transaction commits, in a transaction of its
own: the workspace run lock lasts until the outermost commit, which must not be the
rest of a beat tick. The task checks again that the trigger is enabled, its type is
available and its agent is ready, and logs instead of raising. A message whose formula
fails at run time opens the conversation with the payload and fails the reply with
`trigger_message_failed`, so the list shows why the agent didn't answer.

## Options considered

| Option                                            | Why not                                                                                               |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| A registry of trigger consumers                   | Two consumers exist; a listener list is enough and keeps `Service` ignorant of who owns it.           |
| A reverse foreign key from `Service` to its owner | Breaks the consumer-holds-the-key precedent of nodes, data sources and button actions.                |
| Arm in `after_create` / `after_update`            | Also runs for automation drafts, which must not go live.                                              |
| Owner = the trigger's creator or the run identity | Visibility would hang on one account; deleting it would trash the run log; identities are not people. |
| A trigger-type column on the conversation         | Derivable from the service's content type; stale after a type rename.                                 |
| Store the raw payload next to the opening message | A second source of truth; the periodic payload is two timestamps. Revisit with row triggers.          |
| Leave ask-first tools out of unattended runs      | Silently drops tools the builder allowed; the overlap rule already bounds the waiting replies.        |
| Refuse to arm while any allowed tool asks first   | Blocks the common digest case and leaks approval semantics into arming.                               |

## Consequences

- A new trigger service type needs no agent model or dispatch code. Before it enters
  `AGENT_TRIGGER_TYPES_ENABLED`, its form must be verified in the agent host and its
  reach reviewed: row triggers read tables the builder could read when saving, in any
  workspace, and HTTP and email triggers hand unauthenticated input to a run that may
  use write tools.
- Plugins that overrode `start_listening` or `stop_listening` on a trigger service type
  must override `connect` and `disconnect` instead; the `on_event` class attribute is
  now a method.
- `NULL` owner means shared, not missing. Every site that reads the owner (permission
  subject, timezone, realtime recipient, pending counts, approvals) handles it, and new
  code must too.
- Readers of a shared conversation see what the run identity could read. Builders pick
  the identity knowing that.
- The periodic beat tick only resolves trigger messages; conversations start in tasks
  after it commits. Rate limits and auto-disable follow before other types are offered.
- Follow-ups: editors continuing shared conversations, in-app notifications for their
  waiting approvals, the
  agent-level pause switch, "Run once" and "Last run", HTTP, email and row triggers in
  the picker, per trigger rate limits and auto-disable, the setup wizard's "Run
  automatically" step, the "Who can use it" role settings, a "Row comment is created"
  trigger type, and the `manual` type (hidden until something can start an agent).

## Revisit triggers

- A third consumer of trigger services appears, such as a button field starting an
  agent: reconsider a consumer registry.
- Row triggers ship and readers need the raw payload: add the payload column.
- Agent identities become users: trigger runs keep `created_by=None`, since several
  agents can share an identity and a per-identity cap would throttle them together,
  and keep the trigger's timezone.
