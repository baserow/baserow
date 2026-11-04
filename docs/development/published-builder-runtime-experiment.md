# Published Builder runtime experiment

Measured locally on 2026-11-04 against unchanged develop commit
`4c601aee8ce21420ae0a0fb0cc424a2641dbcb1e`. The primary objective is to keep
published websites from downloading Baserow's authoring dependencies.
This is a local prototype, with no deployment or PR.

The representative published site transfers **62.7% less JavaScript** and makes
**82.0% fewer network JavaScript requests**. It renders nested columns and
containers, a form, a paginated repeat and a record selector backed by a 240-row
table. Source maps of its downloaded scripts contain no Database field types,
GridView, Tiptap, AddElementModal, Chart.js or application plugin implementations.

| Published site, cold context | Develop | Prototype |
| --- | ---: | ---: |
| Transferred JavaScript bytes, including response overhead | 1,783,502 | 665,092 |
| Encoded JavaScript body bytes | 1,757,606 | 659,926 |
| Network JS requests with positive transfer size | 139 | 25 |
| JS resource timing entries, including cache reuse | 142 | 28 |
| Median time to hydrated form controls, simulated network | 4.755 s | 2.087 s |

The timing median uses three fresh Chromium contexts for each build, 80 ms
latency and 1,000,000 bytes/s download and upload throughput. Baseline times were
4.763, 4.755 and 4.693 seconds; prototype times were 2.041, 2.089 and 2.087 seconds.
Both builds used the same local backend, production Nitro server, URL and fixture.
Readiness requires both the form input and completed Nuxt hydration. Resource
totals were collected 1.5 seconds later, including speculative requests.
These are local experimental timings, not a production benchmark or confidence
interval. Warm reload samples transferred no JavaScript in either build.

The other cold routes still render and hydrate. They have smaller transfers but
more requests, which is a tradeoff of prioritizing the public runtime.

| Route | Develop JS bytes / network requests | Prototype JS bytes / network requests |
| --- | ---: | ---: |
| Login | 1,795,792 / 147 | 1,671,155 / 171 |
| Grid | 1,798,482 / 146 | 1,708,731 / 176 |
| Builder editor | 1,798,471 / 146 | 1,727,551 / 179 |
| Dashboard | 1,797,501 / 146 | 1,707,741 / 176 |

The complete client manifest grew from 216 JavaScript entries / 84 dynamic entries
to 264 / 107. Total manifest entries are not a measure of what a published page
downloads. Authoring-route performance was not optimized by this experiment.

The implementation uses a generic `applicationShell` route role and hostname
detection before feature plugin setup. Core, Builder, premium and enterprise
registrations are divided into runtime and application entries. Database,
Dashboard, Automation and agent application plugins and realtime registrations
are imported only for the application shell. A public page does not refresh a
Baserow administrator session; it retains its separate user-source authentication.
Crossing between runtime and shell triggers a document navigation so the required
plugins and stores initialize before the destination renders.

Builder metadata and execution behavior remain synchronous. Editor forms, theme
controls, workflow/service forms and container authoring controls load through
coherent module bundles, with stable async component identities. The formula
execution implementation no longer imports Tiptap; the application entry
registers an editor subclass for the `get` function. Optional graph rendering has
its own import. A production chunk group consolidates the startup/public-page
static dependency graph. The manifest hook disables speculative prefetch for the
application and optional UI bundles while preserving SSR preloads.

Two conditional-rendering changes matter: published columns do not mount the
add-element modal, and collections do not mount refinement headers when all
capabilities are disabled. Enabled public filtering, sorting and searching load
a separate integration feature bundle. It initializes Database registries and
stores once per Nuxt app, including concurrent collections. Initialization is
performed from component setup, not the globally cached async component loader,
so successive SSR requests each receive their own state. This optional feature
still downloads substantial Database code; its dependency footprint is not yet
optimized independently.

Validation completed:

- Production builds succeeded, including the final source implementation.
- `just fix` passed; `git diff --check` passed.
- Nine focused core test files: 1,112 passed, one skipped. Enterprise element
  types: 27 passed. The selected premium calendar specs are entirely skipped
  upstream and provide no validation.
- Isolated runtime tests populate a published Builder and evaluate typed page
  parameters without authoring registrations. Snapshots cover public/editor
  column modal behavior and disabled/enabled collection refinement headers.
- After hydration, public form input retains focus, submitting shows its
  notification, repeat pagination loads Task 010 and the selector selects Task 002.
- Repeated refinement SSR requests each serialize Database state; a subsequent
  ordinary publication does not inherit it.
- An additional publication loads enabled refinements; search reduces repeat
  content to Task 010, and filter/sort contexts open without page errors.
- The editor's formula input focuses, and its insert-element action opens the
  modal with search focus. These actions were dispatched directly to bypass the
  fixture account's onboarding overlay.
- An authenticated public context has no Database field store. Router navigation
  to Grid causes one document reload and initializes that store and the shell.
- Hostname-based public rendering and hydration passed through a Host-preserving
  local HTTP proxy for `test3.getbaserow.io`. Real DNS/TLS was not exercised.
- Authenticated shell routes emit the same hydration mismatch warning on develop
  and the prototype. Published-page checks emit none.

The remaining public runtime is not minimal: it still contains Nuxt/Vue/Vuex,
formula parsing, date/time libraries and shared core controls. Global styles,
fonts and locale loading were not split. Public SSO, optional graph rendering,
preview handoff, every premium view interaction and cross-browser behavior still
need broader QA before treating this experiment as merge-ready. The previous
per-component PR was not rebuilt against these exact fixtures, so these results
compare only with develop.

The isolated prototype is served at `http://localhost:21601`; the normal sample
is `/builder/published/8/`, and the enabled-refinement sample is
`/builder/published/7/`. Backend port: 21600. Raw measurements, build logs and the
fixture manifest are archived in this branch's external memory directory under
`published-runtime-qa/`. No commit or push was made.
