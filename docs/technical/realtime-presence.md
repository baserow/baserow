# Realtime Presence

This document defines the **language and conceptual model** of Baserow's presence feature.

Presence is built on Baserow's WebSocket infrastructure; see [realtime-reliability.md](realtime-reliability.md) for connection lifecycle, reconnection, and event durability. This document reuses its terms (web socket ID, page subscriptions, channel groups) without re-defining them.

Presence answers one question for people working in the same place: **who else is here, and what are they doing?** — bounded by what each viewer is permitted to see.

> **Presence is best-effort and partial by design.** It reflects only what is observable over live connections: who is connected and looking, and their focus. Mutations that arrive through other paths — imports, API calls, data sync, server jobs — have no connection and no focus, and never appear. Presence is descriptive ("who we know is here right now"); it is **never an activity feed, an audit log, or a security/completeness guarantee**. An empty presence space does not mean nobody touched the data.

---

## Terminology

| Term | Definition |
|---|---|
| **Presence** | The feature: who is present on a shared place and what they're doing, bounded by each viewer's permissions. Best-effort and partial — not an activity/audit/security record. |
| **Connection** | One WebSocket connection, identified by a `web_socket_id` at the transport layer. A single user may have several (multiple tabs). |
| **Member** | A connection's representation within a presence space, identified by a `presence_id` (an opaque UUID generated per connection, separate from `web_socket_id`). `presence_id` is the key in Redis, in WS payloads, and in the frontend store. `web_socket_id` is never exposed in presence payloads — it stays in the transport layer for routing and self-echo suppression. |
| **User presence** | The user-visible roll-up: "User X is here," derived by collapsing a space's members by `user_id`. An avatar bar is one way to surface it. |
| **Presence space** | The single logical location presence is tracked for — e.g. one table's grid, whose presence space is `table-42` (Redis key `presence:table-42`, channel group `presence.table-42`). Every connection viewing that location shares one space, **independent of how many data channel groups back it**. One space per location; a presence concept, distinct from any single channel group. |
| **Presence visibility** | The per-recipient decision "should this recipient see that a connection is present *at all*?" Evaluated — depends on how both the observer and the observed entered the space, not a static flag on the connection. |
| **Presence focus** | What one connection is doing within a space — a typed value (e.g. a selected cell) or nothing. Each connection has at most one current focus **per space**; only the latest matters (it is a current state, not a history). |
| **Focus visibility** | The per-recipient decision "should this recipient see this focus?" Lets one space serve viewers with different permissions without leaking what a viewer may not see. |
| **Presence focus type** | A registered kind of focus (e.g. `cell`, `row`) that owns its payload shape, the page types it applies to, and its visibility rule. Pluggable; not owned by any one page type. |
| **Presence focus staleness** | A focus state no longer trustworthy. Enforced client-side, per focus type (e.g. an `editing: true` indicator older than ~30s). |

### Entity relationships

| Relationship | Cardinality | Example |
|---|---|---|
| User → Connections | 1:N | 3 browser tabs = 3 connections |
| Connection → Presence spaces | 1:N | One tab on a table grid and an expanded-row modal |
| Presence space → Members | N:M | A space has 5 members from 3 users |
| Member → Presence focus (per space) | 1:1 | A tab's grid focus and modal focus are independent; within a space only the latest focus is kept |

### Example: one space, many channel groups

Bram (full access) and Davide (a restricted view) both open table 42:

- **Bram** subscribes via the `table` page; his connection belongs to the channel group `table-42`. He is looking at rows 1–100.
- **Davide** cannot listen to the whole table, so he subscribes via the `restricted_view` page; his connection belongs to a *different* channel group, `restricted-view-7`. His view exposes only rows 50–75, and that is what he is looking at.

> **V1 note:** In the initial release, restricted views are **excluded** from presence entirely — `RestrictedViewPageType.get_presence_space_name` returns `None`. This avoids leaking full-access user IDs to restricted view users before a proper asymmetric visibility gate is in place. The example below describes the **target model** for a future version.

Conceptually, they are on different channel groups but interact in the **same presence space**, `table-42`. So, where visibility allows, they see each other:

- Whether Davide sees Bram's avatar at all depends on **presence visibility** — because Davide entered via a restricted view, the visibility rule might hide full-access users from him. Bram, with full access, always sees Davide.
- They see each other's **focus** on rows they can both see (rows 50–75) — **focus visibility**.
- If Bram selects a cell on row 30, Davide does **not** see it: row 30 is outside what Davide may see, so focus visibility withholds it — even though both are in the same space.

---

## The conceptual model

### One space per place

A presence space is a logical location, not a transport channel. The same place (e.g. a table) is delivered to different users over different per-permission channel groups; presence collapses all of them into **one** space so that everyone viewing that place can see each other. A host (today a page type) opts in to presence and declares which logical place each subscription belongs to; permission-tiered entry points for the same place resolve to the same space. Presence is not tied to tables — any place a host enables it for (a grid, a dashboard, a builder page, …) is a presence space; table 42 is just the running example.

### Joining and leaving

A connection becomes present when it subscribes to a presence-enabled place, and is removed when it unsubscribes or disconnects. A connection can be present in several spaces at once (e.g. a grid and an expanded-row modal), each tracked independently; a disconnect clears all of them.

Cleanup leans on the **disconnect signal**, which is reliable because both runtime stacks run a server-side WebSocket keepalive that closes connections which stop responding — so a dead client is detected and removed within seconds, while a merely idle-but-connected client (whose browser keeps answering keepalives automatically) correctly stays present. Any further cleanup is a best-effort backstop, never the primary mechanism. Because presence is best-effort, a connection's mere presence is not guaranteed to be complete or permanent.

### Two-axis visibility

Two independent, per-recipient questions decide what a viewer sees. They compose — a connection must be presence-visible before its focus can be seen at all:

| Axis | Question | Owner | Default |
|---|---|---|---|
| **Presence visibility** | May this viewer see that a connection is present at all? | The place's host | Visible |
| **Focus visibility** | Given the connection is visible, may this viewer see its focus? | The focus type | Visible |

**Presence visibility** is evaluated per recipient — the host determines who sees whom based on how each entered the space. A full-access viewer may see everyone; a restricted viewer may see only others at the same access level. The rule is **asymmetric by design**: who you see depends on your entry point, not theirs.

**Focus visibility** is how one shared space safely serves viewers with different permissions: a viewer sees focus only on the rows and fields they are permitted to see.

Focus visibility is all-or-nothing: a viewer sees a connection's focus in full, or not at all.

### Focus

Focus is what a connection is doing within a space — a single current value per space, replaced on each change, with no history.

Before a focus is shown, three questions are answered, in order:

1. **Is presence enabled here?** — a property of the place.
2. **Does this kind of place support this kind of focus?** — *applicability*, not permission. A grid has cells and rows; a dashboard has neither. Both full and restricted grid views support the same focus kinds and emit them identically.
3. **Is the focus well-formed?** — invalid focus is silently dropped.

**Emitting and seeing are separate.** Which page types may *emit* a focus kind is independent of who may *see* it. Two users on the same grid emit cell focus identically; the difference in what each *sees* is purely the area-visibility rule (which rows/fields each may see), never the page type.

**Staleness** is judged on the client, per focus type: a state implying active engagement (someone is *editing*) stops being shown after a short silence, because it is no longer trustworthy. Passive states linger longer or indefinitely.

---

## Membership

Presence uses **one** space per place and enforces visibility *within* it, per recipient — rather than relying on the permission-tiered split of the data channels. A connection is in a space only because it was already allowed to subscribe to a page that maps there — presence adds no separate permission gate.

---

## Presentation behavior

- **Avatars show unique users**, not connections — multiple tabs of one person collapse to a single avatar, with a deterministic per-user colour. When more users are present than fit, the rest collapse into a counter.
- **A user does not see their own focus** as a presence indicator — the native selection UI already shows it. Their own avatar is **not** shown in the presence bar — only other users appear.
- **Focus highlights** show another user's selected cell or row (with their colour and initials), and an editing indicator when they are actively editing. Highlights render only for what is currently on screen.
- **Focus emission is debounced per space.** Rapid navigation within a space emits only the final position (others see where you land, not each step), and activity in one space never interferes with another. Two purposes: a clean end-state for viewers, and protection against flooding.
- **When several users focus the same target**, their labels collapse into a count.

---

## Future capabilities (permitted, not built)

The model deliberately *reserves room for* these without building them now; each can be added without changing the concepts or the wire-level contract:

- **Filtered focus on restricted views** — showing a viewer only the focus on rows/fields they may see. The focus-visibility rule is the reserved seam; today it passes everything through.
- **Entry-point-aware presence visibility** — visibility rules that depend on how each party entered the space (e.g. restricted viewers not seeing full-access users, admins seeing anonymous public-view users). The evaluated presence-visibility model is the reserved seam. In V1, restricted views are excluded from presence entirely; in V2 they will join with asymmetric visibility (full-access sees restricted users, not vice versa).
- **Stronger cleanup of abandoned entries** — a backstop for the rare case where a disconnect signal is lost. Disconnect remains the primary mechanism either way.


