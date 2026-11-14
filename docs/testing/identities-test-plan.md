# Users and identities: verification and acceptance plan

This plan covers the User-backed identity foundation and terminology changes on
`docs/agent-backing-users-adr`. Starting revision: `0a8a5f1287`.
Verification date: 9 November 2026. Full backend/frontend runs, focused checks and browser verification are complete.
No unresolved identity-feature defect was found after the revocation fix. Full-run
exceptions and remaining verification limits are explicitly recorded below. Comparison base:
`d0571201ad16dc38d7d997eba335f17a906bc043`. The source includes the revocation
fix and additional regressions made during this verification.

The purpose is to establish both sides of every boundary: a human still works,
and an identity works only where nonhuman execution is supported. A passing
identity creation screen alone does not establish that distinction.

## Scope and terminology

- **User** means a human. `User.objects` selects humans.
- **Identity** means a workspace-owned nonhuman record stored in Django's User
  table. `User.objects_and_identities` selects both. There is no separate class
  or type for an identity; `is_identity` tells the two kinds apart at runtime.
- **AnonymousUser** is a separate caller accepted only by specified public paths.
  `None` is not an authorization bypass.
- **Agent application** is the AI application. Its lifecycle is separate from an
  identity's lifecycle. Existing application names remain Agent.
- **Actor/Subject** retain the broader permission meanings, including tokens and
  teams; this change does not redefine them as the User/Identity union.

The ADR describes the eventual design as well as this foundation. The following
are explicitly **not implemented by this branch** and must not be marked passed:

| Future capability | Current expected behavior / acceptance boundary |
| --- | --- |
| Assign identities to collaborator fields or mention them | This foundation still rejects identity collaborator values. Existing human assignment/mention behavior must remain working. |
| Human/identity kind snapshots in every historical display after deletion | Retained User foreign keys and ordinary actor IDs/names are in scope. A distinct persisted kind/badge across every history is a later layer. |
| Bind an Agent application to its execution identity | Application configuration and identity management remain separate; direct shared-tool tests do not prove this future binding. |
| Authenticate machines with dedicated identity MCP/OAuth credentials | Current human credentials must reject identities. The machine-credential mechanism is a later layer. |
| Convert legacy `core.Agent` records automatically | Production has no legacy Agents. Disposable Agent rows are deleted without converting IDs or references; the empty table stays for one release for old processes. |

## How to read results

`PASS — browser` means the actual Nuxt UI called the actual Django API against
isolated PostgreSQL; identity endpoint responses were not replaced with HTTP
fixtures. `PASS — API` means the real DRF endpoint and database were exercised.
`PASS — domain` means real handlers/actions/tools and stored results were exercised.
`PASS — unit` is a narrower component/helper check, possibly with mocks.
`PENDING`, `FAIL`, and `DEFERRED` are not passes. An automated pass is separate
from your acceptance checkbox.

The November 6 review is historical evidence. Fresh commands, outcomes, node IDs,
logs, screenshots and browser traces for this pass are recorded under
`/private/tmp/identity-verification-20261109/`. The final evidence index below will
link each group to concrete tests. Totals from overlapping test runs must not be
added together.

## Test population

Use two separate workspaces, A and B, with ordinary tables and rows. In A prepare
an admin, a second human, an identity with schema-edit permissions, a read-only
identity and a no-access identity. B has its own admin, identity and data. With
RBAC enabled also prepare a team and scoped database/table grants. Keep one
private personal view, one collaborative view, a public form, a template app,
a Local Baserow integration, and an automation with a configured row mutation. Automation configuration tests do not imply
a live automation/provider execution.

Exercise these actor states where the operation accepts that actor:

| Caller | Allowed control | Denied / changed-state cases |
| --- | --- | --- |
| Human admin/member | Normal login, reads and permitted writes | Other workspace, lower role, inactive, pending deletion, revoked permission |
| Identity | Permitted internal/tool/integration work in its single workspace | Other workspace, no access, unavailable role, inactive, trashed, trashed workspace, removed membership, permanent deletion |
| AnonymousUser | Existing template reads and public form submissions | Identity management, private workspace data, ordinary mutations |
| Missing/unknown/stale metadata | No implicit human classification | Fail closed; a missing profile or unknown type must not become human |
| Cached caller or already-used ToolContext | Repeated allowed operations | Disable/trash/revoke through a separately loaded instance, then reuse the context; assert no forbidden read/write |

Run basic permission mode and enterprise RBAC mode. Human-only instance settings,
notifications, member administration, seats and personal ownership are not made
available merely because an identity is an instance of Django User.

## Acceptance checklist

The checkbox is for reviewer sign-off. The execution column records fresh observed results. Evidence keys refer to the
source map below; they are independent of your acceptance checkbox.

| Accept | ID | Scenario and required observable result | Execution |
| --- | --- | --- | --- |
| [ ] | TYPE-01 | Concrete User/Identity annotations cover only the 58 tool-reachable parameters plus ToolContext; nine read/form signatures retain explicit AnonymousUser. Tool schemas still generate correctly. | PASS — source inventory + tool/MCP suites; `execution/annotation-inventory.md`; no nominal type-enforcement claim |
| [ ] | MODEL-01 | Human/inactive-human, active/trashed identity, missing profile and unknown type classify correctly. Default manager excludes identities; inclusive/base managers and foreign keys retain them. | PASS — domain; B-MODEL |
| [ ] | MODEL-02 | User creation creates a human profile; its transaction is code-inspected. Identity creation creates one User, Profile and workspace membership, with unusable password and no staff/superuser status. | PASS — domain + transaction inspection; B-MODEL |
| [ ] | AUTH-01 | Human password/JWT/session login still works; identity password/JWT attempts fail even with a fabricated usable password/token. | PASS — API/browser; B-AUTH, UI-01 |
| [ ] | AUTH-02 | Cached JWT/websocket authentication, current database tokens, MCP endpoint/OAuth and SSO paths keep the human-only boundary. No identity HTTP mutation succeeds with human credentials. | PASS — API/domain; B-AUTH, B-SSO (verified provider result boundary only) |
| [ ] | AUTH-03 | Missing, unknown and stale cached profile metadata fail closed; ordinary human controls remain usable. | PASS — domain/API; B-AUTH |
| [ ] | AUTH-04 | Anonymous and lower-role callers cannot manage identities or access another workspace's identities; denial leaves stored state unchanged. | PASS — API/browser; B-LIFE, UI-07 |
| [ ] | LIFE-01 | Create/list/search/edit/delete identities through UI and API; reload shows persisted state and correct identity avatar/name. | PASS — API/browser; B-LIFE, UI-01–09 |
| [ ] | LIFE-02 | Names at the 150-character boundary, duplicate names, pagination ties, page-size limits and sort/search preserve exact records. | PASS — API; B-LIFE |
| [ ] | LIFE-03 | Failed creation/update with invalid or foreign teams is atomic, including memberships; no partial identity or lost original team/name. | PASS — transactional API; B-TEAM |
| [ ] | LIFE-04 | Trash blocks execution and hides current choices while retaining IDs, membership, grants and historical foreign keys. Restore keeps the same ID and independent disabled state. | PASS — domain/browser; B-MODEL, B-TEAM, UI-08/14/15 |
| [ ] | LIFE-05 | Restore a workspace containing identities; human realtime recipients work and identity membership is preserved. Permanent identity/workspace deletion removes owned records and grants. | PASS — domain; B-MODEL, B-EVENT |
| [ ] | LIFE-06 | Enforce one workspace through supported membership APIs; serialize concurrent team replacement; standalone reassignment/removal is rejected. Corrupt extra memberships fail closed. Raw concurrent ORM membership insertion is not claimed. | PASS — domain; B-MEMBER, B-TEAM; concurrency limited as stated |
| [ ] | PERM-01 | Basic and RBAC defaults, direct roles, scoped roles, team inheritance and direct-role precedence authorize exactly the intended operations. | PASS — domain/API; B-ROLE |
| [ ] | PERM-02 | Cross-workspace teams/scopes and unavailable roles after license changes cannot increase authority; unrelated name edits retain stored role. | PASS — domain/API; B-ROLE, B-TEAM |
| [ ] | PERM-03 | An identity ADMIN never counts as the last human administrator. Human departure, scheduled deletion and workspace cleanup preserve the invariant. | PASS — domain; B-MEMBER |
| [ ] | PERM-04 | Existing context observes disabled/trashed/revoked/deleted actors before the next effect, including prefetched membership paths. No new table/row/field is persisted on denial. | PASS — domain + live integration; E-REVOKE, UI-12/14 |
| [ ] | PERM-05 | Personal views remain human-only through create, adoption, read/edit/publish and import; ordinary human ownership still works. | PASS — domain; B-PERSONAL |
| [ ] | PERM-06 | User/identity/team field-permission choices preserve kind metadata and grant the intended access; no permission data leaks to lower-role callers. | PASS — API/domain + frontend units; B-FIELD; manual selector walkthrough not run |
| [ ] | BILL-01 | Member/admin user lists, seat/free-user counts and license-user assignment exclude identities; team subject counts intentionally include eligible identities. | PASS — API/domain/browser; B-BILL, UI-06; combined UI totals are not seat counts |
| [ ] | BILL-02 | Username/email uniqueness spans humans and identities while human administration targets only humans; collisions return the domain/API error, not a database error. | PASS — API/domain; B-UNIQUE |
| [ ] | EXEC-01 | Paired human/identity tools list apps/tables/schema and create tables with real generated models and persisted schema. Row data is covered separately below. | PASS — domain; E-TOOLS |
| [ ] | EXEC-02 | Paired tool field create/update/delete and linked-field dependency checks persist the right schema and deny unauthorized linked resources. | PASS — domain; E-TOOLS |
| [ ] | EXEC-03 | Paired direct action row create/update/trash/import effects preserve values and actual acting User attribution. | PASS — action/domain; E-ROWS (no row-import ToolContext API exists) |
| [ ] | EXEC-04 | Paired view creation, filters and field/form options persist and read back correctly. | PASS — domain; E-TOOLS |
| [ ] | EXEC-05 | Paired automation workflow/node list/create/update/delete configuration paths work, retain persisted graph edges and enforce workspace scope. No provider/automation run is inferred. | PASS — domain configuration; E-TOOLS |
| [ ] | EXEC-06 | Local Baserow integration run-as resolves an identity, performs the real permitted read/write, and does not fall back to a human after denial/deletion. | PASS — browser/domain; B-INTEGRATION, UI-10–17 |
| [ ] | EXEC-07 | Queued jobs resolve retained identities and recheck current authority after role/membership/disabled/trash changes. | PASS — persisted queued-job execution and four revocations; B-JOB |
| [ ] | ATTR-01 | Created/last-modified User foreign keys and supported action/row-history actor IDs/names identify the actual identity, including after trash. | PASS — domain/browser; E-ROWS, E-HISTORY, UI-17 |
| [ ] | ATTR-02 | Identity work produces required audit/action signals without interactive undo or human analytics; human undo/redo still works. | PASS — domain; E-TOOLS, E-HISTORY, B-EVENT |
| [ ] | ANON-01 | Anonymous template app/table/view/node reads remain allowed only where intended; private equivalents are denied. | PASS — API/domain; E-ANON |
| [ ] | ANON-02 | Anonymous public-form submission works through actual action registration; it does not require an identity or give private-workspace access. | PASS — API/action; E-ANON |
| [ ] | EVENT-01 | Allowed human sessions see identity create/update/delete/team changes; lower roles/outsiders and identities are not human websocket/notification recipients. | PASS — recipient/domain + live browser delivery; B-EVENT, UI-02/04/05/08/09 |
| [ ] | EVENT-02 | Permission-aware broadcasts and AI-provider/group broadcasts target human recipients and avoid per-member profile queries. | PASS — domain + bounded queries; B-EVENT |
| [ ] | IMPORT-01 | Integration publication/import preserves or reauthorizes the supported subject explicitly, trashed identity authorization is denied, and legacy core.Agent authorization is rejected. Personal-view import cannot assign identity ownership. | PASS — domain, scoped contracts; B-INTEGRATION, B-PERSONAL |
| [ ] | MIG-01 | Real migration upgrades existing humans with correct database defaults; rollback refuses while identities exist. Disposable legacy Agent rows are deleted without converting references, and old processes can still query the empty table. | PASS — 2 updated real migration cases (2026-11-12) + drift check; B-MIGRATION |
| [ ] | FLAG-01 | Empty/legacy flags deny creation without writes; identities flag enables it; wildcard behavior is explicit. Existing records remain protected when creation is disabled. | PASS — creation states + existing-record lifecycle with flag disabled; B-FLAG |
| [ ] | SCALE-01 | Identity listing, broadcasts, team bulk membership and custom field grants have bounded query growth; pagination has no duplicates/omissions at tied names. | PASS — bounded query assertions; B-SCALE; opt-in benchmarks not run |
| [ ] | UI-01 | Full identity CRUD/search flows use real API persistence; success/error/permission states and identity visuals survive reload. No uncaught page errors. | PASS — live Chromium; UI-01–09/18 |
| [ ] | UI-02 | Real Members management and integration run-as UI distinguish humans/identities; application creation still calls the AI application Agent. | PASS — live Members/run-as UI; UI-06/10; Agent application naming source/unit checked |
| [ ] | UI-03 | Two admin sessions and a member receive permitted changes through real realtime transport; domain recipient tests exclude callers lacking list permission. | PASS — live delivery + recipient domain tests; UI-09, B-EVENT |
| [ ] | REG-01 | Existing core/premium/enterprise suites, migrations and changed-file lint pass or every exception has explicit attribution and a targeted resolution. | Full runs completed with exceptions; targeted resolutions recorded below |

## Manual browser procedures

Use a disposable workspace or the isolated verification stack. Do not modify a
shared developer/production database to execute these checks.

### M1 — Human account and identity management

1. Sign in as human admin A. Open Members, then Identities. Record the human
   table/API membership rows and identity count separately. The existing Members
   heading/sidebar total intentionally combines humans and identities; it is not
   a human-seat count.
2. Create an identity named `Verification runner`, give it an appropriate role,
   search for it, rename it, and reload the page.
3. Confirm the same ID, saved name/role, identity icon, and unchanged human membership
   rows and seat counts. Open a second admin session and check the visible update.
4. Repeat as a lower-role user and workspace B's admin. Inspect the actual network
   denial for attempted writes; do not rely on a hidden button alone.

### M2 — Team, role and field permissions

1. With RBAC enabled, put an identity in a team and give the team a scoped role.
   Use the same operation as a human control and as that identity through run-as.
2. Change direct and inherited roles in turn. Confirm direct-role precedence,
   no-access denial, and that a foreign team is rejected without losing the
   original assignment.
3. Open a custom field-permission selector. Confirm identity and human choices are
   visibly distinguishable before selection, after save and after reload.

### M3 — Real execution and revocation

1. Configure a Local Baserow integration to run as the identity. Execute a read and
   a write through an existing supported service/action. Query/reload the actual
   target row and inspect supported attribution fields/history.
2. Repeat with a human run-as user, then a no-access identity and another workspace's
   object. Denials must not create or change any row.
3. Reuse an already-started execution context after another session disables,
   trashes, deletes or revokes the identity. The next effect must be denied. This
   timing is reproduced in automated tests when no user-facing long-running
   identity binding exists yet; a fresh-context test is not a substitute.

### M4 — Trash, restore and retained history

1. Record the identity's User ID and an attributed row. Delete the identity from
   settings, confirm it disappears from the live list, and confirm execution fails.
2. Restore it from Trash. Confirm the same ID, role/team membership and row credit.
3. Repeat with an independently disabled identity; restore must not enable it.
4. Trash/restore its workspace, then use a separate disposable workspace to verify
   permanent deletion cleans owned User/Profile/membership/grant records.

### M5 — Human-only and anonymous boundaries

1. Confirm an identity ADMIN does not permit the last human admin to leave.
   Verify seats, member administration and human notifications exclude identities.
2. Confirm an identity cannot adopt another user's personal view or become its
   owner through import. Confirm a human owner still can use that view.
3. In an incognito session, open the configured template/public form and perform
   permitted reads/submission. Attempt the private equivalent and identity settings;
   both must be denied. Inspect the resulting row rather than only a success toast.
4. Attempt identity login with all currently human-only credentials through the
   automated negative cases. Do not issue or expect unsupported machine credentials.

### M6 — Release gate

1. Before deployment, keep `FEATURE_FLAGS` free of `agents`, `identities` and `*` on
   backend/frontend; prevent scripts/internal services from creating identities.
2. Drain every old backend and worker before enabling identity creation. Existing
   identities require avoiding old/new overlap; flag removal does not make rollback
   safe. This gate was explicitly approved after reproducing the old last-admin bug.
3. If this database already ran an earlier version of branch migration 0138, use a
   separately reviewed schema transition. Ordinary migrate will not rerun it.

## Evidence and results index

All artifacts below are local under `/private/tmp/identity-verification-20261109/`.
The tracked regression tests and source map remain reproducible after the disposable
stack is removed. Counts overlap across runs and must not be summed.

| Run | Revision / environment | Result / artifact |
| --- | --- | --- |
| Full backend suite | Frozen final production source; isolated PostgreSQL; 8 workers | **19,483 passed, 2 failed, 321 skipped** in 19m08s — `full-backend.xml`; both exceptions detailed below |
| Foundation/auth/lifecycle/RBAC | Real Django/DRF and PostgreSQL | **817 passed, 6 skipped** — `backend/suite-final.xml`; six explicit opt-in performance benchmarks skipped |
| Focused cache/performance checks | Same production snapshot | **88 passed** — `backend/boundary-final.xml`; included in broader evidence |
| SSO identity/human boundary | SAML/Google/OIDC after verified provider UserInfo, no live IdP | **15 passed** — `backend/sso-boundaries.xml`; includes 9 new cases |
| Queued execution / disabled feature flag | Successful row-containing duplication, four revocations, existing identity CRUD/restore and outsider denial | **27 passed** — `backend/queued-flag-boundaries-final.xml`; includes normal human job controls |
| Shared tools/MCP/anonymous/history | Real effects; complete affected tool/MCP suites | **686 passed** — `execution/final-execution-mcp.xml` |
| Additional paired row CRUD/retained attribution | Added after broad test collection; production unchanged | **2 passed** — `execution/final-row-attribution.xml` |
| Real browser/API/realtime/integration | Dedicated Nuxt, ASGI, Redis/Celery, PostgreSQL; enterprise fixture license | **17 custom checks passed**, zero page errors — `browser/browser-verification.md`, lifecycle/integration traces and `persistence-results.json` |
| Retained Playwright spec | Same dedicated stack, repository fixtures | **1 passed** — `browser/playwright-spec.log`; [identityManagement.spec.ts](../../e2e-tests/tests/identities/identityManagement.spec.ts) |
| Full frontend core | 491 files, 2 workers | **9,135 passed, 1 failed, 2 skipped** — `frontend-core.log`; initial modal timer race described below |
| Full frontend premium | 36 files, 2 workers | **322 passed, 8 skipped** — `frontend-premium.log` |
| Full frontend enterprise | 38 files, 2 workers | **217 passed** — `frontend-enterprise.log` |
| Corrected OAuth modal test file | Actual modal removal awaited, original save assertions retained | **11 passed** — `frontend-oauth-final.log`; not a second full frontend run |
| Isolated periodic-field task suite | Original deadline assertion unchanged; run after full suite stopped | **49 passed** — `field-tasks-isolated.log`; full-run timing outlier not reproduced |
| Corrected import test | Persisted source ID, distinct import and unchanged source assertions | **5 passed** — `grouped-aggregate-import.log` |
| Real migrations | Fast schema fixture disabled, real migration executor | **4 passed** — `migrations/results.xml`; final `makemigrations --check --dry-run`: no changes detected |

Production snapshot is recorded by `final-run-production-manifest.json` (109
branch-related source files), plus focused/browser manifests. No production file
changed after the final backend run began. The two row tests, SSO/queued-job/flag tests and modal
test correction have separate final-source runs. The earlier interrupted backend
run (9,985 passed / 213 skipped) is retained as intermediate evidence and is not a
completed full-suite result.

The full backend skips are recorded in JUnit: 207 scheduled daily cases, 62
opt-in cases, 34 cases excluded by a daily-marker selection, and 18 documented
feature/environment/known skips. Four identity migration cases ran separately.
This is the default complete suite run, not a claim that every opt-in benchmark
or external-runtime case was executed. The test-only corrections received focused
reruns; neither complete suite was repeated afterward.

The browser spec passed before a final cleanup-only improvement that ensures all
owned resources are released even if setup or teardown fails. That adjustment
passed Playwright discovery and formatting; the browser flow itself was unchanged.

## Automated source map

Use these keys with the acceptance table. Each link opens the actual assertions;
function names can be passed to pytest as `path::function`. All parameter variants
in the named focused runs were collected, including both human and identity cases.
The full exact node-ID inventories are in local `backend/coverage-matrix.json`
(172 mapped selectors) and `execution/case-selectors.tsv`; their IDs are local to
those reports and differ from this plan's acceptance IDs.

| Evidence key | Reusable tests / representative exact selector |
| --- | --- |
| B-MODEL | [test_user_identity.py](../../backend/tests/baserow/core/user/test_user_identity.py): `test_user_predicates_distinguish_kind_independently_of_status` (+4 related functions)<br>[test_identity_users.py](../../backend/tests/baserow/core/identities/test_identity_users.py): `test_generated_user_foreign_keys_keep_retained_identity_credits` (+5 related functions)<br>[test_identity_teams.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_teams.py): `test_identity_team_memberships_survive_trash_restore_and_team_edits` (+1 related functions) |
| B-AUTH | [test_identity_accounts.py](../../backend/tests/baserow/core/identities/test_identity_accounts.py): `test_cached_identity_jwt_is_rejected_by_websockets` (+6 related functions)<br>[test_user_handler.py](../../backend/tests/baserow/core/user/test_user_handler.py): `test_loaded_identity_cannot_use_human_password_and_email_flows`<br>[test_token_auth.py](../../backend/tests/baserow/api/users/test_token_auth.py): `test_token_auth` (+2 related functions)<br>[test_user_views.py](../../backend/tests/baserow/api/users/test_user_views.py): `test_token_error_if_user_deleted_or_disabled`<br>[test_users_admin_views.py](../../backend/tests/baserow/api/admin/users/test_users_admin_views.py): `test_admin_user_endpoints_exclude_identity_accounts` |
| B-LIFE | [test_identity_views.py](../../backend/tests/baserow/api/identities/test_identity_views.py): `test_admin_can_crud_search_and_soft_delete_identities` (+7 related functions) |
| B-TEAM | [test_identity_teams.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_teams.py): `test_identity_api_rolls_back_invalid_team_changes` (+1 related functions)<br>[test_identity_concurrency.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_concurrency.py): `test_concurrent_identity_team_replacements_are_serialized`<br>[test_identity_team_permissions.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_team_permissions.py): `test_identity_team_changes_require_membership_permissions` |
| B-MEMBER | [test_identity_subject.py](../../backend/tests/baserow/core/identities/test_identity_subject.py): `test_identity_admin_does_not_replace_last_human_admin` (+3 related functions)<br>[test_user_handler.py](../../backend/tests/baserow/core/user/test_user_handler.py): `test_expired_last_human_admin_deletes_workspace_with_identity_admin` |
| B-ROLE | [test_identity_roles.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_roles.py): `test_identity_member_alias_is_valid_with_rbac` (+7 related functions)<br>[test_subject_role_assignments_views.py](../../enterprise/backend/tests/baserow_enterprise_tests/api/role/test_subject_role_assignments_views.py): `test_list_subject_role_assignments_of_teams_and_identities` (+1 related functions)<br>[test_identity_teams.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_teams.py): `test_identity_direct_workspace_role_overrides_team_role` (+3 related functions) |
| B-PERSONAL | [test_identity_view_ownership.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_view_ownership.py): `test_builder_identity_cannot_modify_or_publish_human_personal_view` (+2 related functions) |
| B-FIELD | [test_field_permissions_handler.py](../../enterprise/backend/tests/baserow_enterprise_tests/api/field_permissions/test_field_permissions_handler.py): `test_custom_field_permission_update_has_bounded_subject_queries` (+2 related functions) |
| B-BILL | [test_license_handler.py](../../premium/backend/tests/baserow_premium_tests/license/test_license_handler.py): `test_identities_cannot_be_assigned_license_seats`<br>[test_enterprise_license.py](../../enterprise/backend/tests/baserow_enterprise_tests/enterprise/test_enterprise_license.py): `test_identity_roles_do_not_consume_seats`<br>[test_workspace_user_views.py](../../backend/tests/baserow/api/groups/test_workspace_user_views.py): `test_list_workspace_users_hides_identities`<br>[test_workspaces_admin_views.py](../../backend/tests/baserow/api/admin/groups/test_workspaces_admin_views.py): `test_admin_workspace_users_and_free_seats_exclude_identities`<br>[test_workspace_views.py](../../backend/tests/baserow/api/groups/test_workspace_views.py): `test_list_workspaces_includes_identity_count` |
| B-EVENT | [test_ws_signals.py](../../backend/tests/baserow/ws/test_ws_signals.py): `test_identity_crud_events` (+2 related functions)<br>[test_ws_tasks.py](../../backend/tests/baserow/ws/test_ws_tasks.py): `test_permission_broadcast_queries_do_not_grow_with_workspace_members` (+1 related functions)<br>[test_identity_ws.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_ws.py): `test_human_team_changes_do_not_broadcast_an_identity` (+2 related functions)<br>[test_notifications_handler.py](../../backend/tests/baserow/core/notifications/test_notifications_handler.py): `test_identity_notification_recipients_are_ignored`<br>[test_posthog.py](../../backend/tests/baserow/core/test_posthog.py): `test_capture_event_action_done_ignores_non_interactive_subject` |
| B-JOB | [test_identity_stored_users.py](../../backend/tests/baserow/core/identities/test_identity_stored_users.py): `test_queued_identity_job_rechecks_current_authority` |
| B-FLAG | [test_identity_views.py](../../backend/tests/baserow/api/identities/test_identity_views.py): `test_identity_creation_requires_current_feature_flag` |
| B-SCALE | [test_field_permissions_handler.py](../../enterprise/backend/tests/baserow_enterprise_tests/api/field_permissions/test_field_permissions_handler.py): `test_custom_field_permission_update_has_bounded_subject_queries` (+2 related functions)<br>[test_user_subject_type.py](../../backend/tests/baserow/core/user/test_user_subject_type.py): `test_user_subject_type_checks_members_missing_from_prefetch` (+1 related functions)<br>[test_ws_tasks.py](../../backend/tests/baserow/ws/test_ws_tasks.py): `test_permission_broadcast_queries_do_not_grow_with_workspace_members`<br>[test_identity_teams.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_teams.py): `test_identity_list_loads_workspace_and_team_summaries_without_per_identity_queries` |
| B-SSO | [test_identity_auth_boundaries.py](../../enterprise/backend/tests/baserow_enterprise_tests/sso/test_identity_auth_boundaries.py) |
| B-UNIQUE | [test_user_handler.py](../../backend/tests/baserow/core/user/test_user_handler.py)<br>[test_user_admin_handler.py](../../backend/tests/baserow/core/admin/users/test_user_admin_handler.py) |
| B-INTEGRATION | [test_integration_types.py](../../backend/tests/baserow/contrib/integrations/local_baserow/test_integration_types.py)<br>[test_service_types.py](../../backend/tests/baserow/contrib/integrations/local_baserow/test_service_types.py) |
| B-MIGRATION | [test_core_migrations.py](../../backend/tests/baserow/core/migrations/test_core_migrations.py) |
| E-TOOLS / E-REVOKE / E-ROWS | [test_identity_tool_context.py](../../backend/tests/baserow/core/tools/test_identity_tool_context.py)<br>[test_identity_roles.py](../../enterprise/backend/tests/baserow_enterprise_tests/identities/test_identity_roles.py) |
| E-HISTORY | [test_row_history.py](../../backend/tests/baserow/contrib/database/rows/test_row_history.py)<br>[test_audit_log_handler.py](../../enterprise/backend/tests/baserow_enterprise_tests/audit_log/test_audit_log_handler.py) |
| E-ANON | [test_anonymous_template_execution.py](../../backend/tests/baserow/core/test_anonymous_template_execution.py)<br>[test_form_view_actions.py](../../backend/tests/baserow/contrib/database/api/views/form/test_form_view_actions.py)<br>[test_application_views.py](../../backend/tests/baserow/api/applications/test_application_views.py) |
| UI-01–18 | [identityManagement.spec.ts](../../e2e-tests/tests/identities/identityManagement.spec.ts) |

Important exact execution selectors in `test_identity_tool_context.py`:

- `test_tool_field_lifecycle_preserves_execution_attribution`
- `test_tool_lookup_dependencies_preserve_execution_attribution`
- `test_tool_view_filters_and_form_options_preserve_execution_attribution`
- `test_tool_automation_lifecycle_preserves_execution_attribution`
- `test_table_import_preserves_execution_attribution`
- `test_row_actions_preserve_execution_attribution_after_identity_trash`
- `test_identity_tools_recheck_a_previously_used_context` (six states × plain/prefetched)
- `test_user_tools_recheck_a_previously_used_context` (two states × plain/prefetched)

The current real migration cases are `test_0138_identity_upgrade_and_guarded_rollback`
and `test_0138_discards_legacy_agents_without_converting_references`. They check old
Agent queries/workspace deletion during rollout, the rollback guard and the removal
of Agent trash entries. `test_0073_deletes_rows_whose_subject_is_a_legacy_agent` and
`test_0043_clears_legacy_agent_authorization` cover the enterprise and integrations
cleanup. The earlier
four-case results above predate the decision to discard disposable legacy data.
`test_identity_indexes.py` additionally interrupts the actual 0139 index build and
verifies that rerunning it recovers the invalid index.
The browser report maps UI-01–17 to specific screenshots, trace actions, HTTP
statuses and persisted row IDs. UI-18 is the retained repository spec.

## Reproduction commands

Run against disposable PostgreSQL databases; never point these verification runs
at a developer or production database. The `just b run` recipe supplies the normal
core/premium/enterprise Python paths. This run used the installed environment with
`UV_CACHE_DIR=/private/tmp/baserow-identity-rename-uv UV_NO_SYNC=1 UV_OFFLINE=1`.

```sh
# Full backend, from the repository root (the recorded run adds a failure-report plugin).
just b run env -u DATABASE_URL DATABASE_NAME=identity_verify_runtime_20261109 \
  python -m pytest -c pytest.ini --reuse-db --create-db -n 8 -q --tb=short

# Focused suites; use the complete path list recorded in the evidence directory.
just b run env -u DATABASE_URL DATABASE_NAME=identity_verify_backend_20261109 \
  pytest -c pytest.ini @/private/tmp/identity-verification-20261109/backend/suite-paths.txt \
  --reuse-db -n 2 -q

# A paired stale-context regression, or substitute any selector from the source map.
just b run env -u DATABASE_URL DATABASE_NAME=identity_verify_execution_20261109 \
  pytest tests/baserow/core/tools/test_identity_tool_context.py --reuse-db -q

# Real migrations: explicitly disable the fast SQL/schema fixture.
just b run env -u DATABASE_URL DATABASE_NAME=identity_verify_migrations_20261109 \
  BASEROW_TESTS_SETUP_DB_FIXTURE=off pytest tests/baserow/core/migrations/test_core_migrations.py \
  -k 0138 --run-once-per-day-in-ci --reuse-db --create-db

just f yarn test:core --run --maxWorkers=2
just f yarn test:premium --run --maxWorkers=2
just f yarn test:enterprise --run --maxWorkers=2
just f yarn test:core --run test/unit/core/components/settings/mcpOAuthConnections.spec.js --maxWorkers=2

# Standard disposable Docker E2E stack, identities enabled and enterprise fixture license.
# Build this branch; the restored schema must include migrations 0138 and 0139.
just e2e build
just e2e up
just e2e test tests/identities/identityManagement.spec.ts
```

The observed browser run used an equivalent dedicated native stack at ports
39991/39992/39993, real migrations, repository Playwright 1.48.0 and Chromium.
Its exact local configuration/scripts remain in `browser/`; it did not run the
entire repository E2E suite. The reusable spec uses the normal E2E fixtures/config.

## Findings discovered during this pass

**V1 — resolved, authorization revocation.** Reusing a successfully used ToolContext
could retain authority after identity disable/trash/pending deletion or workspace
role revocation; removed/deleted identities could still list private applications.
Disabled/deletion-pending humans also retained cached authority. Current
eligibility now comes from the existing batched database lookup. All 16 public
shared tools create an invocation-local permission cache and isolate copies of
the context/user/workspace while retaining request metadata. Paired stale-context
and enterprise role regressions pass, including prefetched membership contexts.

Human-only request list prefetches keep their bounded-query optimization. Existing
query-growth assertions caught an initial N+1 during the fix; the final selected
suite passes those unchanged assertions. Graph tests reload the ORM workflow
between separate calls and verify the same persisted edges. No graph persistence
bug was found.

The guarantee is **the next public shared-tool invocation**, not cancellation of
an operation already executing. Internal human-only Kuma helper compositions retain
their caller cache lifetime. Shared-context concurrency was source-reviewed;
parallel tool-write load testing was not performed.

**V2 — resolved test synchronization, unchanged OAuth UI.** The full frontend run
failed `a slow save does not close the modal of another app` before resolving the
mocked save: a deferred `Modal.hide()` timer could close the newly opened modal.
Both the test and production component were unchanged against the comparison base.
The test now clicks the visible close control and waits for the previous modal's
actual DOM removal before reopening. Its original assertions about the pending
save and second connection remain. The corrected 11-test file passes. No OAuth
production behavior was changed and no second complete frontend pass is claimed.

**V3 — corrected test assumption, unchanged import code.** The full backend run
exposed an unchanged grouped-aggregation import test that assumed a newly allocated
primary key could never equal the arbitrary serialized ID `999`. PostgreSQL
legitimately allocated 999 in the full suite. The regression now imports using an
existing source record's ID and asserts a distinct new record and preserved source.
All three import variants and two related export tests pass: **5 passed** in
`grouped-aggregate-import.log`. The import production code is unchanged; assertions now verify distinct records
and preserved source data.

**V4 — full-suite timing outlier, not reproduced in isolation.** The full backend
run observed 6.97s against the unchanged periodic-field cancellation test's `<4.6s`
wall-clock assertion. Both the test and relevant timeout/task implementation are
unchanged against the comparison base. The entire 49-test field-task file passed
in isolation after the full run stopped, including the original threshold. No
assertion or production code changed. Host/database contention is consistent with
the evidence, but the original failure was not profiled, so suite-state interference
cannot be ruled out conclusively. This remains a full-run exception, not a claim
that the original full suite was green.

## Remaining boundaries and manual sign-off

- Browser evidence is Chromium on the local development stack, not Firefox/WebKit,
  mobile, production deployment, accessibility certification or production load.
- Custom field-permission selector visuals have frontend unit coverage; M2 is still
  available for a reviewer to perform the complete browser walkthrough.
- Browser realtime tests cover permitted human delivery. Negative recipient tests
  calculate real permission-filtered recipient IDs with transport mocked; no live
  unauthorized websocket observer was included.
- SSO tests begin after the external provider has returned verified identity data.
  External identity providers, email and other provider calls were not invoked.
- The queued-job checks load a real stored job and invoke its task synchronously;
  they do not certify broker delivery or worker retries.
- The import tests cover the enumerated current contracts. A full combinatorial
  cross-workspace export/import/duplicate migration rehearsal was not run.
- There is no identity-disable UI/API toggle. Inactive-state regressions deliberately
  modify persisted User.is_active and test denial.
- The approved rollout gate in M6 remains a deployment requirement. It is not
  replaced by a passing migration or feature-flag test.

## Final validation and cleanup

Changed Python source/tests pass Ruff check and format (22 files). The changed
frontend test passes the repository `just f lint` recipe; the E2E spec passes
Prettier and Playwright discovery. `git diff --check`, all source links in this
plan, migration drift and the frozen production manifest are clean. The initial
frontend lint invocation used the wrong path relative to a Yarn script; the
repository's file-scoped lint recipe was then run successfully.

Owned Nuxt/ASGI/Celery/Redis services and the generated browser build directory
have been removed. All **18 task-owned databases** were removed after checking for active connections,
as recorded in local `cleaned-databases.json`; developer databases and services
were not modified.
This plan, permanent regression tests, local logs, JSON/XML and browser traces
remain available. Browser traces contain disposable authenticated test sessions
and should remain local.

## Completion criteria

- Every in-scope acceptance group has a concrete test/result mapping; gaps are named.
- A human control and applicable denied identity/anonymous case accompany each
  shared authority boundary. Denied writes prove absence of stored side effects.
- Tests added during the broad run and production fixes after collection receive
  final-source reruns; the report does not conflate old and final snapshots.
- Browser claims identify the real backend, transport, test-only settings and any
  mocked boundary. No live provider or production-load claim is inferred from them.
- Temporary databases, servers and generated files are removed; reusable tests and
  this plan remain available for review and reruns.
