# AI provider rollout test plan

Use this plan with the [upgrade guide](../installation/ai-providers.md) to collect
release evidence for AI provider configuration and migration. Passing automated
tests or preparing a candidate branch does not establish that an installation is
ready for cutover. Run the rehearsal on an isolated representative installation
with approved test data and provider accounts. Keep credentials, customer content,
and connection values out of reports and shared logs.

## 1. Record the candidate and baseline

Record the candidate commit and image digest, the exact previous image intended for
rollback, enabled extensions, database size, migration state, deployment topology,
backend/frontend/worker configuration, and browser asset versions. Use protected
references for configuration and backups instead of copying their values into the
report. Record approved thresholds for request failures, task failures, latency,
queue age, migration lock duration, and cutover time before running the rehearsal.

Exercise every applicable starting state:

| Starting state | Candidate verification |
|---|---|
| Working environment and workspace JSON, no database providers | Upgrade without imports; supported legacy consumers still use their intended account and model |
| Database providers coexist with legacy settings | Precedence is verified and differences are reconciled; stale credentials, missing models, or disabled features cannot change behavior unnoticed |
| Database providers and scoped feature settings | Existing provider overlays and feature settings retain their behavior |
| Missing, incomplete, conflicting, or stale configuration | Expected unavailable states and importer warnings are recorded; no unintended fallback account is used |
| No AI configuration | Upgrade and non-AI workflows work; consumers show their expected unavailable state |

## 2. Inventory before imports or repairs

Run the read-only management command in the candidate's backend environment:

```bash
just b manage audit_ai_provider_settings
just b manage audit_ai_provider_settings --workspace-id <id>
```

The JSON includes stored provider/model and feature-setting metadata, legacy source
presence, integration/publication identifiers, AI Agent selections, and AI Fields
when Premium is installed. The scoped form includes instance settings and that
workspace's publications. Trashed records are marked; unbound services appear only
in the global inventory. The command neither changes configuration nor calls
providers, and does not print keys, endpoints, prompts, or raw provider errors.
Treat a successful exit as inventory completion, not a readiness verdict. Supplement
it with the owner and runtime checks below; it cannot inspect native Kuma credential
validity, live provider accounts, deployment behavior, or rollback compatibility.

Inventory the following using identifiers and configuration-presence metadata only:

- Instance and workspace database providers, enabled models, feature eligibility,
  workspace inheritance switches, and Kuma selections or explicit disables.
- Legacy environment and workspace provider sources, including malformed/incomplete
  entries, and Kuma's separate model and provider-native credential sources.
- AI Fields, formula-suggestion access, Kuma chat/onboarding, and AI Agent services
  in editable Builder and Automation applications. Include trashed integration
  references that can be restored through undo/redo.
- Every live Builder domain and Automation publication with an AI Agent consumer,
  including the source application, publication identifier, integration identifier,
  intended owner, selected provider/model, and override classification.

Classify integration settings as inherited, complete with explicit models, complete
with omitted models, explicitly empty models, or partial. A complete published blob
does not reveal whether it was an inherited snapshot or an intentional override:
record its provenance as unknown until the owner confirms it. Inventories cannot
prove credential validity or which remote account will answer a request.

Compare effective model availability and intended connection sources on the previous
image and candidate. Resolve or explicitly accept every difference. In particular,
incomplete workspace JSON must not silently borrow credentials, complete integration
connections must not borrow optional settings, and models outside an effective
allowlist must fail before a provider call. Verify installed third-party provider
contracts separately. Use the
[integration override matrix](kuma-model-settings-test-plan.md#65-explicit-integration-overrides).

## 3. Migrations and imports

Start separate copies from the same protected baseline for the no-import and import
paths; reusing an already-imported copy does not test an untouched upgrade.

1. Apply all candidate migrations. Measure elapsed time and database lock behavior
   on a representative provider-model population while previous-version traffic is
   exercised. Verify previous code remains compatible with the retained schema.
2. Check `core.0120` on existing models with empty, nonempty, and unknown feature
   values: it adds `ai_agent` once and preserves other values and enabled states.
   Historical migration tests cover reversal; deployment rollback retains the schema.
3. Without imports, run every consumer in section 4, including a workspace with
   complete legacy settings and one with incomplete settings. Confirm that an empty
   provider administration page does not hide continued legacy runtime use.
4. On the import copy, run the instance and workspace previews from the upgrade
   guide. Compare database state before/after to confirm no writes. Review every
   incomplete-setting and conflict warning without retaining credential values.
5. Under the final settings write pause, apply instance then workspace imports.
   Verify each scope is atomic; failure in one scope does not imply the other was
   rolled back. Imported models receive `ai_fields` and `ai_agent` eligibility.
6. Rerun previews and imports: existing configurations stay unchanged. In the isolated
   rehearsal only, change a legacy source after import and confirm the importer
   reports the difference instead of synchronizing over the database provider.
   Reconcile the intended final configuration explicitly.
7. Confirm imports leave legacy workspace settings available for rollback, do not
   rewrite integrations or publications, and do not select Kuma's legacy model.

## 4. Real-provider consumer checks

Use the intended account and endpoint, recording redacted provider request references
or an approved account-side observation. A successful text response alone does not
prove the correct connection was used. Run each applicable consumer with inherited
instance and workspace models, then with disabled or unavailable selections.

| Consumer | Required evidence |
|---|---|
| Provider administration | Save and test models; text features pass text probes, Kuma also makes a real tool call; failures are actionable and stale success clears after connection/model edits |
| AI Fields | Existing and new text/choice fields generate; bulk/background and auto-update generation complete; supported attachment generation works; removed eligibility blocks generation |
| Formula suggestions | Existing picker offers AI Fields-eligible models, produces a usable formula with the intended connection, and rejects unavailable models; no separate formula feature/default is required |
| Kuma | Instance/default and workspace inherit/override/disable work; a conversation executes a tool; onboarding uses instance scope; unconfigured/invalid selections use the verified legacy fallback, explicit disable never does |
| Automation AI prompt | Editor execution and live workflow execution resolve inherited and explicit connections correctly; scheduled/queued execution after deployment agrees |
| Builder AI prompt | Editor, preview, and every live domain execute correctly; public pages do not require editor-only integration state to render valid actions |

Check enabled workspace models overriding matching instance models, non-overridden
instance models retaining their own connection, disabled workspace models suppressing
matching identifiers, and workspace-provider disable revealing the inherited layer.
Restore removed eligibility and verify saved Agent selections recover without being
reselected. Trashing an integration must prevent execution; restoring it must
reconnect the saved service. Keep explicit complete integration overrides in the
matrix because central eligibility does not govern their explicit model list.

Run the [Kuma model settings plan](kuma-model-settings-test-plan.md) for detailed
permissions, scoped defaults, realtime, and error assertions, and the
[AI Field plan](ai-field-test-plan.md) for generation variants. Confirm staff-only
instance access, workspace-admin scope isolation, member denial, and no credential
values or inherited connection settings in API responses or websocket frames.

## 5. Publications and owner-approved cutovers

Keep one baseline publication unchanged while its source draft has unrelated pending
edits. Verify it continues to run its original content and compatibility snapshot;
editing the source integration alone must not be reported as a live cutover.

For another publication, preserve the intended live version and have its owner
approve the exact current draft. Republish that application and verify that inherited
settings now follow live workspace credentials and eligibility. Rotate a test key
and remove/restore AI Agent eligibility to demonstrate this with real requests and
blocked requests. A deliberate complete override must retain its own connection.

Record every deferred publication, its owner, verified connection, and reason for
deferral. Keep its credentials valid and test it independently. Unknown provenance
or an unapproved draft must not trigger an unattended republish. Retained snapshots
must not be reported as controlled by central credentials or model eligibility.

## 6. Backend, workers, and browser cutover

Rehearse the actual deployment sequence under the settings write pause. Keep schema
changes compatible with previous code, and route representative requests/tasks to
both versions during any proposed overlap. Compare the intended connection,
availability, and disable decisions; a health check alone is insufficient.

Where previous and candidate behavior cannot be made equivalent, stop the proposed
rolling path and prepare a coordinated cutover. Do not describe an untested
mixed-version deployment as zero downtime.

Record when each old web, backend, worker, scheduler, and frontend process drains,
including in-flight tasks and queue handling. Import or change provider configuration
only after incompatible writers have drained. Confirm active administrator/editor
browsers reload to candidate assets before writes resume. Old browser bundles remain
old after server replacement; test that the rollout procedure actually updates them.
Before adding provider types unknown to older clients, include all affected users in
the reload requirement.

## 7. Rollback with the actual previous image

1. While still isolated, rotate database credentials and delete an imported workspace
   provider. Confirm these do not synchronize legacy configuration: deletion removes
   the matching workspace JSON entry. Restore a verified compatible configuration
   for the intended rollback path without exposing its values in the report.
2. Check database-only providers/models, Kuma disables, feature eligibility, workspace
   suppression, and existing/fresh publications against the actual previous image.
   A legacy path must not re-enable an intentionally disabled consumer or use an
   unintended provider. Stop rollback if equivalent behavior cannot be established.
3. Pause relevant writes, deploy the recorded previous image with its rehearsed
   configuration, retain the schema and provider rows, drain candidate processes,
   and reload browsers.
4. Repeat real-provider checks for AI Fields, formula suggestions, Kuma, and editable
   and published Agents. Verify task queues and non-AI workflows, record recovery
   time, and compare it with the agreed threshold. Reapply the candidate to confirm
   recovery does not depend on a one-way or destructive repair.

## 8. Stop/go record

Keep a protected evidence record with these fields for each applicable scenario:

| Scenario | Candidate/previous digest | Expected behavior | Observed result and redacted evidence | Duration | Owner | Status |
|---|---|---|---|---|---|---|
| Example: no-import workspace upgrade | Fill in | Intended provider/model retained | Fill in after execution | Measured | Named reviewer | Not run |

Stop for unexplained connection changes, credential disclosure, unauthorized scope
access, unavailable active consumers, unintended re-enablement, unapproved
publication changes, unresolved importer warnings, migration/queue thresholds being
exceeded, or a failed rollback. Explicitly document accepted compatibility overrides
and their owners; acceptance does not make them database-managed.

Proceed only when applicable checks have recorded passing evidence, deviations have
reviewed resolutions, the previous image and usable legacy configuration remain
available, and the release owner approves the measured deployment and recovery plan.
Mark skipped or unavailable checks as outstanding. This document is a procedure,
not a record that any deployment or real-provider rehearsal has passed.
