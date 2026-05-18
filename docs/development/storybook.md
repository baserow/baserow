# Storybook

Baserow's component library — the canonical place to see what the
design system offers without spinning up the full app. Useful when:

- You're picking which existing component to use ("is there already a
  badge for this?").
- You're building a new component and want to verify it renders in
  isolation.
- You're reviewing a frontend PR and want to see the component
  variants visually.

For the deployed version, browse
[baserow.io/style-guide](https://baserow.io/style-guide).

## Run it locally

From `web-frontend/`:

```bash
just storybook
```

That wraps `yarn storybook` (defined in
`web-frontend/package.json`). Storybook starts on
**[http://localhost:6006](http://localhost:6006)**.

If you're running `just dev up`, Storybook is started alongside the
backend, Celery, and frontend services automatically. Check logs with
`just dev logs -f storybook`.

## Where stories live

Stories live in `web-frontend/stories/` as `*.stories.js` files,
typically one per component. A quick browse:

```
web-frontend/stories/
├── Alert.stories.js
├── Avatar.stories.js
├── Badge.stories.js
├── Button.stories.js
├── ButtonIcon.stories.js
├── …
```

Each file follows the Storybook 9 CSF (Component Story Format) — a
default export with `title`, `component`, `args`, plus one named
export per variant. Copy the closest existing file when adding a
new component story.

## Adding a story for a new component

1. Create `web-frontend/stories/<ComponentName>.stories.js`.
2. Import your component and define the default export (title,
   component, default args).
3. Add named exports for the variants worth showcasing — default
   state, loading, disabled, error, with-icon, etc.
4. Run `just storybook` (from `web-frontend/`) and verify your component renders.
5. Open a PR — design reviews start from Storybook.

The
[`write-frontend-unit-test`](skills-index.md)
skill covers component testing; Storybook is the visual companion.
A new component generally needs both.

## What's not in Storybook

- Whole-page screens (those need the running app to wire up routing,
  auth, and realtime).
- Components that depend on Vuex store state — only if you can pass
  the dependencies through props.
- Anything coupled to the dynamic-model machinery (field cells, row
  views). The store-bound versions live in the app; Storybook holds
  the presentational primitives.

## Related

- [Frontend architecture](../patterns/frontend-architecture.md) —
  where components fit in the broader layering.
- [Project conventions](conventions.md) — BEM SCSS, Vue 3 render
  function rules.
- [Tools — Storybook](tools.md#storybook) — version info and the
  underlying configuration.
