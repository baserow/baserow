# Realtime Presence — Technical Reference

> Companion to [realtime-presence.md](realtime-presence.md) (concepts, terminology, model). This holds v1 scope decisions and design rules that guide implementation. Read the conceptual doc first; concepts are not repeated here.

---

## V1 scope

What is enabled in the first iteration. The conceptual model permits all combinations; these are the v1 choices.

| Place | Presence (who's here) | Focus | Notes |
|---|---|---|---|
| Regular table grid | Visible | Visible across the whole table | Default |
| Restricted view | Visible | Visible only for rows/fields the viewer may see | Same space as the underlying table; the focus-visibility rule filters by area |
| Password-protected shared view | Visible | Visible | Authenticated members behave like a regular grid |
| Public view | **Disabled** | **Disabled** | Presence is not enabled — no space, no events |

Presence visibility is pass-through in v1 — everyone in a space sees everyone. The evaluated-per-recipient model (see conceptual doc) is the reserved seam for future entry-point-aware rules.

---

## Design rules

Three gates on an inbound focus, checked in order:

1. **Is presence enabled here?** — `PageType.can_have_presence`, checked at subscribe time.
2. **Does this page type support this focus kind?** — `PresenceFocusType.compatible_page_types` (applicability, not permission). Gates **emission** by the emitter's page type; reception is gated only by focus visibility.
3. **Is the focus well-formed?** — valid dict, matching type key, JSON-serializable, within size limit. Invalid focus is silently dropped.

**Emitting and seeing are separate.** Emission is gated by the emitter's page type (gate 2); what each recipient *sees* is gated by focus visibility — a per-recipient predicate, pass-through in v1.

**Transport is focus-type-agnostic.** Storage and broadcast treat a validated focus as an opaque dict. Focus types (payload shape, applicability, visibility) live in the domain layer. New focus types register without touching transport.

---

## Reserved seams

Additive — each can be enabled without changing the conceptual model or the wire contract:

- **Entry-point-aware presence visibility** — the host evaluates `(observer's entry point, observed's entry point)` to decide who sees whom. Example: restricted viewers not seeing full-access users, admins seeing anonymous public-view users. The conceptual model already defines this as an evaluated predicate; v1 passes everything through.
- **Focus-visibility filtering** — the focus type evaluates whether a given focus should be shown to a given recipient (e.g. area-bounded focus on restricted views). The `can_emit_to` predicate is the seam; v1 returns true.
- **Stale sweep** — pruning entries whose `last_seen` exceeds a threshold. Staleness is already detected on read; enabling the prune is a threshold decision, not a shape change.

---

## Development note

Both runtime environments (Daphne in development, the ASGI server in production) run a **server-side WebSocket keepalive** that closes unresponsive connections — so the disconnect-driven cleanup works in both; only the exact timing and log signatures differ. When testing cleanup, trigger a real disconnect (close the tab, kill the socket, drop the network) rather than relying on keepalive timing — and note that development auto-reload drops sockets on every code change, which is unlike a long-lived idle connection.
