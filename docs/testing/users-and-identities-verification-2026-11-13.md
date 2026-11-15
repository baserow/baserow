# Users and identities: release verification, 13 November 2026

This is a fresh execution plan for the complete local identity stack: foundation,
history/picker polish, collaborator and mention support, notification sender
metadata, and the latest selector cleanup. Earlier verification results in
`identities-test-plan.md` are historical evidence, not passes for this run.

## Rules and baseline

- Freeze and record the exact commits and any included patch before execution.
- Commit the already-approved implementation. This pass makes no product fixes.
- Run in the clean stack worktree and isolated disposable databases. Browser
  verification uses a separate test stack, never shared developer data.
- Keep passing human controls beside identity allow/deny cases. Exercise anonymous
  callers only where the existing public/template contract permits them.
- Classify each failure as a product defect, a test defect, an environment problem,
  or unresolved. Record expected result, rationale, observed result, reproduction,
  affected revision, and a potential fix. Never silently change code or expectations.
- `PASS` requires fresh execution. Skipped, blocked, untested and historical checks
  are separate statuses. A test plan cannot prove behavior in every possible state.

The user explicitly included all current identity changes, including the newer
identity-binding permission policy. The first baseline was `5f76b42b43`; results
from it remain comparison evidence. The final implementation baseline is
`2856ef1a7b` (foundation `fdb697c545`, polish `dce43b81b9`), compared with
`22cabd4917`. It is frozen in `/private/tmp/baserow-identity-readiness-final`.
The only restack conflict was resolved by retaining the newer, approved
inherited-access implementation and its tests. Evidence directory:
`/private/tmp/identity-readiness-20261113/`.

## Coverage matrix

| ID     | Area                                     | Expected behavior and why                                                                                                                                                                                                                                                                                                       | Verification                                                                                                                            |
| ------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| MODEL  | Classification and managers              | Human defaults exclude identities; inclusive/base managers retain identities and attribution. Missing or unknown kind never becomes human. Identity has one workspace, unusable password, no staff/superuser authority.                                                                                                         | User identity/subject tests; core identity suites; member/admin API suites.                                                             |
| AUTH   | Human authentication                     | Password, JWT, refresh, cached HTTP/WS, API token, MCP/OAuth and SSO paths continue to admit valid humans and reject identities. Old human cache payloads reload rather than causing permanent denial.                                                                                                                          | API authentication/cache/token suites; user tests; SSO identity boundary tests; websocket and MCP authentication tests.                 |
| LIFE   | Identity CRUD and lifecycle              | Search/pagination are stable; create/update are atomic; trash/disable/delete removes execution eligibility while restore retains IDs and independently disabled state. Last human admin and workspace deletion invariants hold.                                                                                                 | Core/enterprise identity, workspace/member and trash suites; real browser CRUD/realtime test.                                           |
| SELECT | Selection and management                 | New selections exclude inactive, trashed and pending-deletion identities. Management/historical lists retain their intended records. Every paginated selector forwards its selection filter.                                                                                                                                    | Identity API, Agent configuration, collaborator metadata, identity service and Local Baserow form tests.                                |
| PERM   | Basic/RBAC/team/field access             | Direct/scoped/team grants authorize the intended operation in the owning workspace only; unavailable roles and foreign subjects fail closed. Subject role and field-option queries remain useful after generic endpoint removal.                                                                                                | Basic permissions; role/team/field permission API/domain suites; frontend subject/team/role suites.                                     |
| BIND   | Run-as authorization                     | Agent picker returns only numeric id/name, never people. Only identity managers may create or replace a binding. Other application editors may keep or clear it, and their picker contains no identities. Duplicates and snapshots obey the same policy. Unavailable saved authorization never silently switches to the editor. | Agent configuration/API permission/import tests, Local Baserow tests, frontend configuration and browser run-as.                        |
| EXEC   | Actual effects and revocation            | Human and identity tools/integrations perform real permitted schema/data actions with correct actor attribution. Reused contexts and queued work recheck revoked, disabled, trashed, pending-deletion or removed actors before the next effect.                                                                                 | Tool context, local integration services/dispatch, job, anonymous/template and row/action tests.                                        |
| COLLAB | Assignment and mentions                  | Identity support is opt-in per collaborator/long-text field. Only eligible workspace identities can be assigned. Turning support off removes stored assignments/defaults and undo restores them. Rich text/comments can mention identities without notifying them.                                                              | Identity collaborator/export suites; multiple-collaborator field/API suites; editor/store/cell units; browser collaborator test.        |
| ATTR   | History and notifications                | Actual actor name/type survives supported history snapshots, including deletion. Identity senders show identity metadata/avatar; identities never receive human email/in-app notifications. Human and deleted sender rendering remains correct.                                                                                 | Audit/row/automation history; notification, field notification and premium row-comment suites; avatar/history frontend units.           |
| IMPORT | Import/export/duplicate/publish/snapshot | Supported same-workspace copies preserve authorization; portable imports reauthorize explicitly; unavailable identity and legacy core.Agent bindings do not gain authority. Collaborator values/defaults remap correctly.                                                                                                       | Identity export suites; Agent/Builder/core import, publish, duplicate and snapshot tests; Local Baserow legacy import cache regression. |
| HUMAN  | Human-only behavior                      | Seats, free-user counts, admin lists, personal ownership, interactive undo, analytics, websocket recipients and notifications exclude identities where required. Existing human behavior remains usable.                                                                                                                        | Premium license, enterprise license/ownership, user/admin/action/posthog, realtime and notification suites.                             |
| FLAG   | Flags and editions                       | Disabled creation flags prevent writes; existing identities remain protected. Basic, enterprise, custom-role and license-loss behavior remains coherent.                                                                                                                                                                        | Identity feature flag, role/license and selector tests.                                                                                 |
| MIG    | Migrations and rollback                  | Existing humans receive safe defaults. Disposable legacy Agents are removed without converting references; retained table supports old cleanup. Rollback refuses existing identities; concurrent-index retry works; no migration drift.                                                                                         | Real core/enterprise/integration identity migrations, history kind migration, index tests and makemigrations --check.                   |
| SCALE  | Bounded queries and pagination           | Identity/team/field metadata and realtime recipients avoid per-item profile queries; tied names paginate without duplication; legacy imports reuse the cached user query.                                                                                                                                                       | Existing query-count/pagination/concurrency tests with exact command evidence.                                                          |
| UI     | Real browser contracts                   | Human login, identity management/realtime, Agent selection/reload/trash and opt-in collaborator interactions call real APIs and preserve stored state. Check Chromium and Firefox where available.                                                                                                                              | Playwright identity lifecycle/run-as/collaborator specs with traces; frontend suites for affected components/stores.                    |
| CLEAN  | Submission checks                        | Correct local stack ancestry; no removed subject endpoint/role projection callers; no whitespace/lint issues; no unexpected source mutations during test execution.                                                                                                                                                             | Scoped static checks, source manifest, Git diff/status and semantic review.                                                             |

## Execution groups

1. Backend identity, user/auth, membership, role/team/field permissions and licenses.
2. Backend Agent/integration/tools, collaborator/history/notification, import/export
   and relevant anonymous controls. Include human equivalents, not identity-only probes.
3. Websocket timing and real migration tests separately, avoiding shared-database
   interference and distinguishing runner flakes from product failures.
4. Core, premium and enterprise frontend suites spanning the affected features.
5. Real Chromium/Firefox identity workflows against code matching the recorded SHA.
6. Source audit, lint, formatting, migration drift and source-integrity checks.

Exact commands, selected paths, exit codes, JUnit/JSON reports and logs will be
saved beside the evidence. Run independent checks even if one group fails. Repeat
only a failing case or checks affected by a new diagnostic hypothesis.

## Failure report format

For each finding record:

- Severity and whether it prevents declaring this stack ready.
- Expected behavior and its contract/source.
- Actual result with a minimal reproducible command and evidence.
- Root cause if established; otherwise the remaining uncertainty.
- Whether introduced by this stack or present in its comparison base.
- Potential fix, without applying it.

## Results

**Verdict: not ready.** The new binding policy has a confirmed snapshot-restore
bypass (R1). Verification also encountered existing test isolation problems and a
local Firefox startup failure. No implementation or test-expectation fixes were
made during this pass. The verification run is complete within the limits below.
R1 was fixed after this pass; see its resolution.

| Check                                              | Result                                       | Interpretation                                                                                                                                |
| -------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Final combined backend selection                   | 2,885 passed, 48 failed, 18 skipped          | Every one of the 48 failures passes in a fresh-process rerun. The combined run remains red; see T1/T2.                                        |
| Isolated backend reruns                            | 399 passed, 1 skipped across 15 files        | Overlaps the combined selection; do not add these counts to its total.                                                                        |
| Final websocket/cache/index checks                 | 90 passed                                    | Includes the earlier websocket timeout, old cached human profiles, identity rejection and interrupted-index recovery.                         |
| Legacy integration cleanup SQL                     | 1 passed                                     | Executes migration 0043 against human, identity and legacy Agent bindings, including an overlapping numeric ID.                               |
| Focused real migration cases                       | 8 passed                                     | Identity upgrade and guarded rollback, legacy Agent cleanup, three history columns, Agent run-as cleanup and typed integration authorization. |
| Core frontend matrix                               | 447 passed in 28 files                       | Final source, including notification avatar, identity settings/store/service, Agent configuration, collaborators and history.                 |
| Premium frontend                                   | 322 passed, 8 existing skips after retries   | Full earlier-baseline suite plus final retries of both failed files.                                                                          |
| Enterprise frontend                                | 267 passed after retries                     | Full earlier-baseline suite plus final sharing/inherited-access retries.                                                                      |
| Browser workflows                                  | Chromium 3 passed; Firefox 3 launch failures | Firefox tests never reached application behavior.                                                                                             |
| Static checks / migration drift / source integrity | Passed                                       | No tracked source mutations during execution; only report/memory changes in the main checkout.                                                |

The frontend totals contain **1,036 distinct passing cases and 8 existing skips**,
counting parameterized cases separately and removing repeated runs. Between the
earlier and final baselines, only Local Baserow authorization selection and the
inherited-access summary changed on the frontend; both were retested on the final
baseline. This is not a claim that the full core frontend or whole monorepo passed.

### R1 — Snapshot restore uses the creator's identity-binding authority

- **Severity:** High; blocks declaring the new binding policy complete.
- **Location:** `backend/src/baserow/core/snapshots/handler.py:465`,
  `SnapshotHandler.perform_restore`; caller
  `backend/src/baserow/core/snapshots/actions.py`, `RestoreSnapshotActionType.do`.
- **Expected:** The person restoring an Agent snapshot must have `identity.update`
  to retain its identity binding. This is the newly approved policy, and direct
  duplication already applies it to the copying person.
- **Trigger:** A workspace administrator creates a snapshot of an Agent bound to
  an identity. Another human is a workspace Viewer and an Admin on that Agent.
  The second person can restore its snapshots but cannot bind workspace identities.
  The administrator can subsequently clear the original Agent's binding.
- **Observed:** `check_can_bind` returns false for that person. Direct duplication
  correctly clears the binding, but restoring the administrator's snapshot retains
  it. The temporary test fails with `Actor denied binding; direct duplicate cleared
it, but snapshot retained identity 3`. This also reproduces after the administrator
  clears the original binding through `AgentService.update_configuration`.
- **Why:** The action receives the restoring user but does not forward that user
  to the handler. The new import configuration sets
  `copied_by=snapshot.created_by`, authorizing with the snapshot creator instead.
  This alternate entry point was unrestricted before the new policy; the new
  commit secures direct duplication but leaves this route using another actor.
- **Potential fix:** Pass the restoring actor from the job/action through
  `perform_restore`, use that actor for `copied_by`, and check the restore and
  binding permissions against that same actor. Preserve the snapshot's creator
  as historical metadata. Add controls for authorized and unauthorized restorers
  and for permission changes between job submission and execution.
- **Evidence:** `probes/test_snapshot_binding.py`,
  `snapshot-binding-app-admin.xml` and `snapshot-binding-revocation-final.xml`, with
  their logs, in the evidence directory. The probe
  uses the real role manager, duplicate handler, snapshot export/import and restore
  action; no permission mocks. It also reproduced with a custom role lacking the
  identity-update operation.
- **Resolution:** The restore action passes the restoring person to
  `perform_restore`, which checks that person's restore permission and hands them
  to the import as `restored_by`. The Agent keeps its binding only when they may
  bind identities. `copied_by` stays unset on restore, so credential checks keyed
  on it behave as before. Covered by
  `test_a_restored_snapshot_keeps_run_as_only_for_identity_managers`,
  `test_a_snapshot_restore_keeps_apps_the_restorer_cant_read` and
  `test_restore_snapshot_checks_the_person_restoring`.

### T1 — Existing tests leak model mocks into the shared service registry

- **Expected:** A test must leave shared service definitions usable by later tests.
- **Observed:** The final combined backend run contains 35
  `TypeError: issubclass() arg 2 must be a class...` failures. The earlier run also
  failed schema generation with `AttributeError: __name__`. The affected files
  pass when run in fresh processes.
- **Why:** Existing tests in
  `backend/tests/baserow/contrib/integrations/local_baserow/test_service_types.py`
  assign `Mock()` to shared `model_class` attributes without restoring them. A
  subsequent uncached registry lookup or schema traversal consumes that mock.
  This test file is unchanged from comparison base `22cabd4917`.
- **Potential fix:** Use scoped monkeypatching or temporary subclasses and restore
  registry caches when definitions change. Keep a test-order regression proving
  a real service lookup/schema generation still works afterwards.
- **Evidence:** Both broad-run XML reports, isolated reruns, and the temporary
  `probes/test_registry_pollution.py`. This is a test defect, not 35 independent
  application failures. It still prevents describing the combined suite as green.

### T2 — Role fixtures and asynchronous controls fail under the combined run

- **Expected:** Role-dependent tests start with valid role rows/cache state; Agent
  resume tests observe the completed synchronous test run.
- **Observed:** Eight permission tests encounter absent role rows or cached IDs
  referring to absent roles in both combined runs. Four Agent resume assertions
  in the final run see `running` instead of `completed`. These files are rerun
  separately without changing source or assertions, and all pass. A workflow test
  also saw zero created rows in the combined run and passes in isolation.
- **Cause:** Role failures are order-dependent fixture/cache state; the exact
  preceding polluter is not isolated. The asynchronous failures require separate
  classification from the confirmed registry corruption.
- **Potential fix:** Make role setup/cache reset explicit for the consuming tests;
  for transient asynchronous controls, await the relevant completion boundary
  rather than relying on process scheduling. Diagnose before changing assertions.

One unrelated premium AI-field modal assertion initially saw an open modal after
the outside click was expected to close it. It passes unchanged in the final
30-case premium retry. Its exact cause was not established; a potential test fix
is to synchronize with the close event/rendered state if a controlled reproduction
confirms a timing issue. Do not change product behavior based on that single run.

### T3 — Broad historical migration rollback encounters a missing table

- **Expected:** The older integration migration tests can reach their historical
  schema and then apply the migration they exercise.
- **Observed:** The broad migration lane reported two failures while reversing
  older schemas. PostgreSQL rejected `ALTER TABLE
baserow_premium_localbaserowtableserviceaggregationgroupby DROP COLUMN mode`
  because the table did not exist. This lane was terminated; it has no completed
  JUnit result and is excluded from passing migration totals.
- **Cause/status:** Unresolved historical-schema/rollback mismatch. It was not
  established whether this also happens on the comparison base, so it is not
  attributed to the identity change. The final focused migration lane is separate.
- **Potential fix:** Reproduce the older integration targets with matching premium
  migration targets. If the test constructs an inconsistent historical state,
  correct that setup; if a supported reverse path is invalid, correct the reverse
  operation. Neither change was made during this review.
- **Evidence:** `migrations-real.log` and `migrations-broad-db-errors.log`, including
  the two exact PostgreSQL errors at 13:53:13 and 13:57:50 UTC. The replacement
  migration runner uses a clean clone of the repository E2E schema dump upgraded
  to the final source; it does not fake the transitions under test.

### E1 — Firefox cannot launch in this local environment

- **Expected:** Chromium and Firefox both run the three identity browser workflows.
- **Observed:** Chromium passes all three. Firefox times out in
  `browserType.launch` before reaching application setup or any UI assertion.
  Its trace reports `sandbox_extension_issue_file_to_process ... Operation not
permitted`, `Can't find profile directory`, and a headless framebuffer failure.
- **Potential fix:** Run these unchanged specs in the supported Linux/CI Playwright
  environment, or repair the local Playwright Firefox installation/runtime.
  No application change is justified by this startup failure.
- **Evidence:** `e2e-final.log`, `e2e-final.json`, and browser traces under
  `e2e-results/` in the evidence directory. Firefox coverage remains unverified.

### Runner adjustments

- The first migration attempts failed before the intended checks: an overlong
  derived database name, then a fast-schema setup without pgvector. A shorter
  disposable name and `BASEROW_TESTS_SETUP_DB_FIXTURE=off` run real migrations.
  The final eight cases pass using a clean current-schema template, configured
  before the direct migration database setup. The temporary runner changes only
  database creation; the tests execute their actual forward/reverse migrations.
- The broad core frontend run was interrupted after it expanded to hundreds of
  unrelated files. Its partial log is not counted as a completed suite. The final
  focused matrix covers every changed core frontend spec plus authentication
  controls: 28 files, 447 tests passed.
- Premium and enterprise startup hooks exceeded 120 seconds under concurrent
  machine load. The final focused retries use one worker and
  `--hookTimeout=300000`; product source, test assertions and test-body timeouts
  remain unchanged. The inherited-access and sharing-input retry passes all
  13 tests.
- The initial serial websocket lane had one timeout (64 passed, 1 failed). The
  final serial lane, including WS authentication/cache and concurrent-index retry controls,
  passes all 90 tests.
- Final scoped backend Ruff/format checks pass (247 files); frontend ESLint,
  Prettier and Stylelint pass. `git diff --check` passes and
  `just b check-migrations` reports `No changes detected`.
- Source searches found no remaining generic subject endpoint/client, obsolete
  Agent subject-option DTO, or dead subject-role projection callers. Shared
  subject queries still serve team/role, audit and field-permission APIs.

### Reproduction commands and evidence

Backend commands use the shared virtual environment and unique disposable
databases on `localhost:5431`, with `UV_NO_SYNC=1` and a task-local uv cache.
The exact 52-path backend selection and command are in `backend-paths.json` and
`backend-final-command.json`; execute with `python run_backend_final.py` from the
evidence directory. `run_isolated.py` and `run_extra.py` rerun failing files in
fresh processes. These are diagnostic scripts outside the submitted source.
The eight real migration cases and exact command are recorded in
`migrations-focused-command.json`; results are in `migrations-focused.xml` and
`.log`. The temporary `probes/migration_template.py` changes database setup only.

The blocking permission probe can be rerun from the final worktree with the same
environment as the backend matrix:

```sh
just b test /private/tmp/identity-readiness-20261113/probes/test_snapshot_binding.py \
  -q --tb=short
```

The focused frontend path list and exact commands are in
`frontend-focused-paths.json`, `run_frontend_focused.py` and
`frontend-focused-results.json`. Browser execution uses the final CI images:

```sh
just e2e build
just e2e up
just e2e test tests/identities/ --project=chrome --project=firefox \
  --workers=1 --trace=on --reporter=list,json
```

The browser stack explicitly uses frontend/backend ports 3070/8070 and the
`baserow_e2e_` cookie prefix. It owns disposable containers and test data only.
The production/developer stacks were not changed.

### Limits

This is broad, targeted release verification, not proof of every possible state.
The whole monorepo and full core frontend were not completed. Existing skipped
cases remain skipped; Firefox behavior and the older historical rollback failure
remain unresolved. Query-count/concurrency controls were exercised, but no
production-scale load or live rolling deployment was performed. SSO/OAuth and
human-only licensing were checked through repository tests, not live external
identity providers or a separate SaaS billing deployment.
