# Frontend review

Use this reference for Vue components, stores/composables, mixins, frontend service
types, browser behavior, routes, translations, and SCSS.

## Component and state ownership

- A component owns rendering, input wiring, and truly local ephemeral UI state.
  Persisted rules, cross-surface domain behavior, shared async state, and mutations
  belong in the owning store, composable, registry/type, or service layer.
- Keep one authoritative copy of state. Derive views with computed values; do not
  copy injected/prop state and then reconcile two versions or fall back between
  stores.
- Generic components receive normalized capabilities such as `readOnly`; they do
  not discover product, public/authenticated, premium, or enterprise context by
  reaching into parents or unrelated stores.
- Components declare the props and events they use. Avoid `$parent`, DOM reach-ins,
  another store's mutation names, or `$refs` as a domain API; expose a method or move
  the behavior to its owner.
- Frontend validation, emptiness, permissions, and result/error shapes match the
  backend contract, including missing versus empty values.

## Async and transition behavior

- Track concurrent operations independently. A request carries the owning resource
  identity and generation/revision; a stale completion must not overwrite a newer
  edit, replacement, route, or reopened editor.
- Abort or ignore outdated requests, prevent accidental duplicate in-flight work,
  and attach retry/reset behavior to the visible/open lifecycle rather than assuming
  a component mounts only once.
- Pending, partial, unavailable, and failed states are visible and truthful. A failed
  save preserves the user's edits and keeps a recovery path; newer outcomes replace
  stale errors and instructions.
- Realtime updates flow through the regular store/type update path rather than a
  second per-component implementation.

## Interaction and accessibility

- Use native interactive elements where possible. New controls are reachable and
  operable with Tab, Enter, and Space, have an accessible name/state and visible
  focus, and restore focus correctly when overlays close.
- A blocked submit exposes and focuses the actionable error, including errors inside
  collapsed sections. Follow the existing lazy-validation behavior instead of
  showing warnings before the user can act.
- Keyboard events in an editor act on the input, not grid navigation. Grid-cell
  buttons use the established `mousedown` behavior so selection and editing do not
  race the click.
- If the component renders user-controlled rich text, HTML, URLs, files, or external
  results, load the security reference and exercise the persisted browser sink.

## Repository conventions and evidence

- UI copy changes only English locale files. Type classes obtain copy through the
  application i18n instance; do not build dynamic translation keys.
- SCSS lives in the appropriate bundle, not a Vue `<style>` block. Use BEM and
  `$palette-*`; ensure pseudo-elements do not collide with existing sorted, filtered,
  or grouped indicators.
- Route by name through the router. Encode URL path and query components separately;
  never stringify composite field values into a URL.
- New components and meaningful changes get focused tests of rendered behavior and
  user interaction, including the relevant pending, error, permission, and keyboard
  path. Prefer a unit test for local behavior and an e2e only for a real cross-layer
  workflow.
- CSS fixes to geometry, clipping, stacking, or responsive layout need browser
  evidence at the affected sizes. Use stable bounding-box assertions or screenshots
  when practical; otherwise record the exact manual matrix and residual gap.
- For grid, virtual-list, drag/drop, or responsive changes, use realistic row/field
  counts and the applicable long-content, mobile, Safari, and row-height cases. Load
  the data-performance reference when reactive work repeats per cell or item.
- Dependency changes are installed through Yarn so `yarn.lock` is generated rather
  than edited by hand.
