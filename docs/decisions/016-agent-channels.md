# ADR 016: Let people talk to an agent through channels

|        |                                                |
| ------ | ---------------------------------------------- |
| Status | Proposed                                       |
| Date   | 2026-11-25                                     |
| Issue  | https://github.com/baserow/baserow/issues/6259 |
| Author | Davide Silvestri (@silvestrid)                 |

## Summary

An agent answered workspace members on its own page and reacted to triggers. Nobody
could talk to it from anywhere else, or without an account. We add channels: a channel
is a place outside the agent's page where people hold a conversation with it, starting
with a public chat page. A channel is its own concept beside triggers, not one more
trigger type, because a trigger reacts once to an event and a channel carries a
conversation that continues.

## Context

ADR 014 made a trigger single-shot: one event starts one new conversation, the agent
reacts and stops. Its dispatcher, overlap rule and queue all assume that. A member's
conversation is the opposite, a person writes, reads the answer and writes again, but
it needs an account and a role on the agent.

The first design for a public chat made it one more trigger service type, next to the
HTTP trigger. It was dropped before any code: every follow-up message would have had
to be an event that continues a conversation, which no trigger does.

Agent Builder is behind `FF_AGENT_BUILDER` and has no production users.

| Term         | Meaning                                                                                  |
| ------------ | ---------------------------------------------------------------------------------------- |
| Channel      | A place outside the agent's own page where people talk to it and get its replies.        |
| Channel type | What a channel is: `public_chat` first, `website_widget` next, a messaging app later.    |
| Public chat  | The channel type that is a page with its own link.                                       |
| Visitor      | The anonymous person writing through a public chat. Not a user, and has no account.      |
| Run identity | The subject the agent's tools act as (ADR 013). Never the visitor.                       |

In scope: what a channel is and how it differs from a trigger, where a type keeps its
data, who is behind a visitor's reply, what a visitor sees and how they prove a
conversation is theirs, and where the code lives. Out of scope: limits of any kind
(rate, message count, expiry), any type but the public chat, and members writing in a
visitor's conversation.

## Decision

### 1. A channel is not a trigger

What tells them apart is where the agent's reply goes:

- A trigger starts a job from an event. The reply is a record members read, anything
  sent outside goes through a tool, and the next event starts a new conversation.
- A channel carries a conversation. The reply itself goes back to whoever wrote, and
  their next message continues the same conversation.

The same app can be both. "Talk to the agent in a messaging app's thread" is a channel:
the thread is one conversation and the reply is posted in it. "When a message lands in
this room, triage it" is a trigger. A row comment is a trigger today: each comment
starts a new conversation and the agent comments through a tool.

So a message that arrives through a channel starts its reply at once, as a member's
does. Channels use no fan-out task, no lock, no overlap rule and no queue. A second
message while the agent is still replying is refused. A reached workspace run limit
refuses the message, because it can be sent again, where a trigger records a failed
reply.

### 2. A channel holds what every channel has; its type holds the rest

`AgentChannel` belongs to one agent and holds only an enabled switch and its type.
Each type keeps its own data in a subclass with its own table, the way services and
auth providers do. The public chat's subclass holds the link, the optional password,
and the title and welcome text its visitors see; a messaging app's would hold its
workspace and room instead.

Code that only needs to know whether a channel is on reads the base table. Code that
lists channels loads the subclasses in one query per type, never one per channel.

### 3. A visitor's reply has no member behind it

A conversation a channel started is shared and has no owner, like a trigger's (ADR 014,
decision 2). It is marked `started_by_channel`, and its `channel` foreign key is set to
null when the channel is deleted. The visitor's messages have the role `visitor` and no
sender.

The reply runs with `created_by=None`, on the authority of the channel: it stops with
`channel_off` once the channel is switched off, trashed or deleted. Its tools act as
the agent's run identity. Ask-first tools are held as in any run, and the visitor
waits until someone who may approve tool calls decides.

Unlike a trigger's reply, somebody reads it while it is written. The agent is told it
talks to an anonymous visitor whose messages are outside data, and that the team, not
the visitor, decides held calls, so a member's reason is never passed on. `ask_person`
is not offered: the person to ask is in the conversation.

Members read a visitor's conversation, decide its held calls and stop its replies.
Nobody writes in it, workspace admins included, because the visitor's page shows only
the visitor's and the agent's messages.

### 4. A visitor sees text only

The visitor API exposes a message's id, role, content, status and time. Steps, tool
calls, approvals, error codes, senders and other conversations stay private.

The answer streams only when the reply can't call a tool. What a reply writes before
it calls a tool isn't its answer, and can't be told from the answer while it arrives,
so a reply that can call tools keeps its text out of the stream and the visitor gets
the answer whole when it ends. The agent is told its answer goes to someone outside
the workspace and to put in it only what may be shared with them.

A channel that can't be used answers "not found" whatever the reason: unknown link,
switched off, trashed, of a type the workspace can't use, or its agent or workspace
gone.

### 5. The link gives access, a token says whose conversation it is

Anyone with the link can talk to the agent; a password is optional. Starting a
conversation returns a token signed the way public views and dashboards sign theirs,
with a key made from the link, the password hash and the instance secret, and carrying
the conversation's id. A conversation's id alone opens nothing, and a changed password
ends every open visitor conversation.

The page keeps the token in the browser's local storage, not in a cookie, so it also
works framed on another site.

### 6. Channel types are a registry

The base model, the type registry, the reply path and the builder API live in the
core agent module. A type registers itself with its model, as in every other registry:
the `public_chat` type, its anonymous API and its page come from the enterprise module.
Core asks the registry whether a type can be used in a workspace.

The visitor's stream is mounted under `/api/chat-runs/`, the prefix split deployments
already route to the async server.

## Options considered

| Option                                               | Why not                                                                                           |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| A public chat as a trigger service type              | A trigger never continues a conversation; the dispatcher, overlap rule and queue would lie.       |
| The link, password and title on the channel itself   | A messaging app has none of them; every later type would carry empty columns.                     |
| A JSON column for what a type needs                  | A request finds its channel by the link, which needs a unique indexed column.                     |
| The conversation's uuid as the visitor's proof       | It shows in members' addresses and logs, and can't be ended by changing the password.             |
| Members write in a visitor's conversation            | The visitor would read answers to messages they can't see. Taking over needs a role they can see. |
| A cookie for the visitor's token                     | Browsers block it when the page is framed on another site.                                        |
| Every tool asks first in a visitor's conversation    | It overrides what the builder set; the builder chooses per tool, knowing the channel is public.   |

## Consequences

- Anyone with the link can ask for whatever the run identity can read, and run every
  allowed tool that doesn't ask first. The instructions are a soft guard, not a
  boundary. Builders pick the identity and the ask-first tools knowing that, and the
  channel's settings say so.
- There are no limits yet, so an anonymous person can spend the AI budget, fill the
  run queue and hold the stream slots members share. This is accepted while the
  feature is in beta and must be solved before the "Beta" label comes off.
- A message's `unattended` flag now means that no member is behind the reply. Whether
  somebody reads it while it is written depends on what started the conversation.
- Channels are not exported: a duplicated, imported or restored agent has none, and
  its copied conversations keep `started_by_channel`.
- Next, in its own PR: an "answer the visitor" tool. A reply that can call tools sends
  its answer by calling it, only that text goes to the visitor, as it is written, and
  everything else the reply writes stays in the members' view. Members also get a way
  to see a conversation as its visitor saw it.
- Follow-ups: limits, the Website widget type, how a public chat looks (a logo and a
  colour), replacing a link without deleting the channel, members taking over a
  conversation, and exporting channels.

## Revisit triggers

- A row's comments should be one conversation the agent answers in: make row comments
  a channel type. Its writers are members, so its replies run for them.
- Members need to take over a visitor's conversation: add a message role the visitor
  can see.
- The "Beta" label comes off: decide the limits first.
