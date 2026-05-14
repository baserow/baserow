# Editions and licensing

Baserow ships in three editions. They share most of the code but differ in
what's enabled at runtime. This page covers:

1. The boundaries between core, premium, and enterprise — what goes where
   and why.
2. The licensing mechanism — how the code knows whether a feature is
   active.
3. The SaaS context — how baserow.io differs from a self-hosted install.

## Editions

| Edition | Folder | License | Contents |
|---|---|---|---|
| **Core** | `backend/`, `web-frontend/` | Open-source (MIT) | Everything everyone gets: users, workspaces, the database application type with all built-in field/view types, the builder app, automations, dashboards, integrations. The framework. |
| **Premium** | `premium/` | Baserow Premium Edition License | Self-hostable but licensed features: personal views, row comments, AI fields, advanced exports, etc. |
| **Enterprise** | `enterprise/` | Baserow Enterprise Edition License | RBAC, SSO/SAML, audit logs, advanced admin, restricted views, data scanner, etc. |

Premium and enterprise are themselves Baserow plugins — they register types
into the same registries the core code uses. There is no special code path
that "is premium" or "is enterprise" beyond a licence check at the feature
boundaries.

## Boundary rules

**The single most important architectural rule in the project:**

```
core   ──> can be imported from anywhere
contrib ──> may import from core, never the other way
premium ──> may import from core and contrib, never the other way
enterprise ──> may import from core, contrib, and premium, never the other way
```

In particular:

- **Core code must never import from contrib, premium, or enterprise.** Core
  should be agnostic about which application types or licensed features
  exist. The way features extend core is by *registering into core's
  registries* from their own `apps.py` `ready()` methods.
- **Contrib must never import from premium or enterprise.** Same reason.
- **Premium and enterprise extend the platform**, they don't modify it. If
  you need to change core behaviour to make a premium feature work, you
  refactor core to provide a registration point — you don't reach into
  premium from core.

Why it matters: a Baserow user who self-hosts core-only must be able to run
without `premium/` or `enterprise/` on disk at all. The licence model also
depends on it — a premium feature can't run if `premium/` isn't installed.

## Where things go

The rule of thumb when you're adding a new feature:

- **Touches everyone:** core or contrib.
- **Touches paid plans on self-hosted *and* on SaaS:** premium.
- **Touches paid plans only on SaaS or enterprise self-hosted:** enterprise.
- **Touches the database application type:** `contrib/database` (for free) or
  `premium`/`enterprise` (for paid).
- **Touches the builder, automations, dashboards, integrations:** the
  corresponding `contrib/<area>` folder.

When in doubt, ask. Putting a feature in the wrong folder is hard to undo
because users get used to having it available on their plan.

## The licensing mechanism

The licence system lives in `premium/backend/src/baserow_premium/license/`.
This is deliberately not in core — core knows nothing about licensing. Code
that needs to gate behaviour on a feature flag imports the `LicenseHandler`
from premium.

### Models

- **`License`** (`baserow_premium.license.models.License`) — one row per
  installed licence. Holds the encoded licence token; decoding gives the
  product code, valid-from / valid-to dates, granted features, and seat
  count.
- **`LicenseUser`** — many-to-many between `License` and `User` for
  per-seat licences.

### `LicenseType` — the registry

Each kind of licence is a `LicenseType` registered in `license_type_registry`
(also in premium). Today there are two:

- `PremiumLicenseType` (`baserow_premium.license.license_types`).
- `EnterpriseLicenseType` (`baserow_enterprise.license_types`).

A `LicenseType` defines which features it grants, the product code stored on
the licence, and behaviour like seat assignment rules.

### `LicenseHandler` — the API

`baserow_premium.license.handler.LicenseHandler` is the entry point for
checking features. Three patterns of use:

```python
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.license.features import PREMIUM

# Instance-wide check (no workspace context).
if LicenseHandler.instance_has_feature(PREMIUM):
    ...

# Workspace-scoped check.
if LicenseHandler.workspace_has_feature(SOME_FEATURE, workspace):
    ...

# User-scoped check inside a workspace.
if LicenseHandler.user_has_feature(SOME_FEATURE, user, workspace):
    ...

# Raising variant — recommended in handlers/services so failure
# turns into a clean HTTP response via the exception mapping.
LicenseHandler.raise_if_user_doesnt_have_feature(SOME_FEATURE, user, workspace)
```

The handler delegates to a "license plugin" abstraction so the implementation
can vary between standard self-hosted, SaaS, and test environments. The
default plugin lives in premium; SaaS overrides it with its own variant.

### Feature constants

Each plugin keeps its feature flag constants in a `features.py`:

- `premium/backend/src/baserow_premium/license/features.py` — `PREMIUM`,
  `AI`, `PERSONAL_VIEWS`, `EXPORT_GROUP`, ...
- `enterprise/backend/src/baserow_enterprise/features.py` — `RBAC`,
  `SSO`, `AUDIT_LOG`, ...

Use these constants by import. Don't pass raw strings.

### Failing closed

`LicenseHandler.raise_if_*` raise `FeaturesNotAvailableError`, which the API
exception mapping translates to a clear "feature not available" response.
This is the right behaviour for new feature checks — fail closed, not open.

A handler that needs to gate behaviour on a feature looks like:

```python
class MyHandler:
    def my_method(self, user, workspace):
        LicenseHandler.raise_if_user_doesnt_have_feature(
            SOME_FEATURE, user, workspace,
        )
        # ... the actual work
```

## SaaS context — baserow.io

The hosted product (baserow.io) is a different deployment of the same
codebase, plus a private repository (`baserow-saas`) that overrides some
behaviour:

- **Trials and billing.** SaaS users land on a trial; expiry transitions are
  handled by SaaS-only code. The free / paid plan distinction in SaaS is
  enforced through the same `LicenseHandler` API, but with the SaaS
  licence plugin doing the actual lookup against subscription state instead
  of installed licences.
- **Account-management UI.** Self-hosted admins manage licences in their
  admin panel; SaaS users manage their plan through Stripe-driven flows in
  `baserow-saas`.
- **Marketing pages.** baserow.io serves marketing content. Self-hosted
  doesn't.

Most code paths run identically in both environments. When SaaS-specific
behaviour is needed in shared code, register a hook in core and let SaaS
implement it — same pattern as premium/enterprise vs core.

## Common mistakes

- **Importing `LicenseHandler` from core.** Don't. Core code must not depend
  on premium. Instead, refactor: expose a hook in core, register the
  feature-gated behaviour from premium.
- **Hard-coding feature strings.** Use the constants in `features.py`. Strings
  drift; constants don't.
- **Checking the license inside a tight loop.** The check is cheap but
  non-zero. Cache the result for the request via `local_cache` (see
  [caching](caching.md)).
- **Forgetting that premium / enterprise files don't exist in core-only
  installs.** Conditional imports must be defensive; do not assume
  `baserow_premium` is importable from a core code path.
- **Putting a paid feature in the wrong tier.** Premium vs enterprise is a
  product decision, not an engineering one. Check with PM before deciding.

## Related

- [Systems overview — license/feature/pricing system](systems-overview.md#license--feature--pricing-system).
- [Directory structure](../development/directory-structure.md) — the boundary
  rules in the broader codebase layout.
- [Architectural patterns](../patterns/architecture.md) — where the licence
  check belongs in a request (in the service or at the start of the action,
  not in the view).
