# ADR 013: Workspace-level integrations

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-29                                     |
| Issue        | https://github.com/baserow/baserow/issues/6015 |
| Author       | Tsering Paljor (@paljort)                      |
| Contributors |                                                |

## Summary

Integrations currently belong to individual applications, so the same SMTP connection or Local Baserow identity must be configured and maintained separately in every app that uses it.

Admins will be able to create workspace-level integrations or promote existing ones for use across applications in the workspace. A hidden shared application will own them, preserving the existing `Integration → Application → Workspace` model.

Published apps and workflows will receive independent copies; duplicates and snapshots within the workspace will retain their references. Workspace exports and templates will flatten workspace integrations to the app level.

## Context

Integrations hold the credentials and identity that services in Builder apps and Automations use, such as an SMTP connection or a Local Baserow identity. Every integration belongs to exactly one application today, so an editor who uses the same connection in several apps sets it up and maintains each copy independently.

Workspace admins need to configure such an integration once and make it available to every app in the workspace, either by creating it at workspace level or by promoting an integration that already exists in an app, which makes that integration available to the whole workspace while the original app keeps using it. App builders need to pick it when configuring a service, the same way they pick an app-level one. Credential changes should reach every editor app without being re-entered.

In scope for v1:
- Workspace integration management and use.
- Promotion from an app.
- Behaviour during publishing, duplication, snapshots, workspace export/import, templates and trash.

Immediate follow-ups to v1:
- Usage counts on delete.
- Removal of lazy creation and the backfill task, once a data migration guarantees every workspace has a shared application.

In scope for v2:
- Publishing credential changes independently of app changes.
- Bulk replacement of references.
- Builder-managed sharing.

### Glossary

| Term                  | Meaning                                                                                |
| --------------------- | -------------------------------------------------------------------------------------- |
| App                   | Any application that can own integrations: a Builder app, an Automation, etc.          |
| Shared application    | The hidden application owned by a workspace.                                           |
| Workspace integration | An integration owned by the shared application.                                        |
| Promotion             | Making an integration that belongs to one app available to every app in the workspace. |
| Published copies      | Published Builder apps, published Automation workflows and workflow test clones.       |

## Decision

### 1. A hidden shared application owns the workspace integrations

Each workspace will have one hidden application of a new `shared` type. New workspaces receive it when they are created. Existing workspaces are backfilled by a background task after deployment, and until that task has reached a workspace, listing its applications creates the shared application if it is missing.

A workspace integration remains an ordinary `Integration` owned by this shared application. `Integration` has a foreign key to `Application`, and existing code depends on that ownership chain: Local Baserow uses `application.workspace` for context, application types determine the supported integration types, services validate integration ownership when saved, imported and dispatched, and publishing, duplication and snapshots go through export/import. Keeping the chain intact retains that behaviour and the existing permission scoping without a second lookup path, and follows the Builder's hidden `__shared__` page precedent.

The shared application remains accessible through existing application managers and APIs but is hidden from user-facing application lists. It cannot be managed as an ordinary application, and features such as exports, templates, trash listings and statistics must explicitly exclude it where appropriate. Workspace integrations use the existing integration API and are managed through Workspace settings.

In the trash, a workspace integration is listed under the workspace; the shared application is never shown as a parent.

The background task does the one-off backfill in batches after the rollout, instead of a data migration that would run before it. Until the task has reached a workspace, the new code can meet a workspace whose shared application does not exist yet, which is what the lazy creation in the listing covers. Its downsides are small for one release: a write on a read endpoint, taken under the workspace row lock so that concurrent listings cannot create two, and code that is soon obsolete. The next release adds a data migration that creates any missing shared applications and removes both the lazy path and the task.

### 2. A service or user source may use an integration of its own application or of the workspace

Ownership validation will accept an integration owned either by the application of the service or user source, or by the shared application of the same workspace.

Cross-workspace references remain invalid. Integration selectors will distinguish app-level and workspace-level choices.

### 3. Published copies get their own copy, duplicates and snapshots keep the link

Publishing copies each referenced workspace integration into the published copy as an app-level integration. Published content therefore does not depend on an editable workspace integration: changing or deleting the workspace integration cannot directly disrupt a published copy.

The trade-off is that credential changes, including urgent rotations, do not propagate to published copies. Each affected app or workflow must be republished until integration-only publishing is available; a full republish may also expose unrelated changes that are not ready to go live.

By contrast, duplication and snapshot creation/restoration within the same workspace retain the workspace integration reference. They use its current configuration, not a historical snapshot of its settings. This reference-preserving rule does not apply to workspace imports or templates, even into the same workspace (decision 4).

### 4. Workspace exports and templates flatten to the app level

Workspace exports and templates include referenced workspace integrations as app-level integrations, with sensitive fields stripped using the existing export rules.

Each imported app receives its own copy; shared ownership is not preserved, even when importing into the original workspace. Local Baserow copies are re-authorised to the importer, while integrations such as SMTP require their credentials to be configured again.

This retains a common export/import path and avoids leaving services without integrations after import. The cost is duplication: three apps using one workspace integration produce three app-level integrations on import. Consolidating them afterwards is an Admin task using the ordinary tools: promote one copy and repoint the other services to it, by hand in v1 and with bulk replacement once it exists. Import itself will not recreate workspace-level ownership.

### 5. Admins manage, Builders list

Workspace-scoped permissions will allow Builders to list and select workspace integrations, while only Admins may create, update, order, delete or restore them. The operations are separate from app-level integration permissions: because the shared application belongs to the workspace, reusing existing Builder-level operations could unintentionally grant management rights over integrations used by other apps.

### 6. Every integration type is allowed at the workspace level

The shared application will support all integration types. In particular, a Local Baserow integration authorised as a person will make that identity clear wherever it is selected (for example, “Runs as [person] in all applications in this workspace”).

This deliberately makes an authorised identity usable across applications: a Builder who can select the integration may use capabilities available through that identity. The Admin-only management rule and visible identity are the v1 controls; this broader reach is an accepted security consequence.

### 7. Promotion only, as a one-row move

An Admin may promote an existing app-level integration by moving its `application` reference to the workspace's shared application. Promotion moves the existing integration rather than creating a copy, preserving existing references. Only Admins may promote integrations. The original app's services and user sources continue to work under decision 2; published copies remain unchanged.

Promotion is undoable unless new services or user sources began referencing the integration after the move, in which case moving it back could break them.

For a Local Baserow integration authorised as someone other than the promoting Admin, promotion must re-authorise it as the Admin or be rejected. Workspaces with duplicate integrations can promote one and manually repoint other apps' services to it in v1. Bulk replacement is deferred to v2. Demotion is not offered; an Admin who wants to stop sharing an integration deletes it and recreates it at the app level.

## Options considered

| Option | Reason not chosen for v1 |
| ------ | ------------------------ |
| Add workspace ownership to `Integration`, or introduce `WorkspaceIntegration` | Creates a second ownership path across existing consumers, permission scopes, integration types and trash handling. |
| Hide the shared application in backend managers | Requires separate lookup paths for APIs and consumers that need to resolve it; we instead hide it in the frontend and explicitly exclude it where necessary. |
| Create the shared application by a data migration before the rollout | Blocks the deployment until every workspace is processed; the background task does the same work in batches after the rollout, with lazy creation covering the gap. |
| Let published copies directly reference workspace integrations | Shared edits or deletion could immediately affect live apps and workflows. |
| Omit workspace integrations from exports | Imported services would lose their integrations, with no bulk repair path in v1; templates also need portable copies. |
| Deduplicate workspace integrations through a dedicated export manifest section | Requires additional import handling, workspace integration creation and Admin permissions, while promotion and bulk replacement consolidate copies after import anyway. |
| Reuse app-level integration permissions | Could allow Builders to manage shared integrations through the existing ownership chain. |
| Let Builders manage workspace integrations | Shared changes affect multiple applications; v1 uses the stricter Admin boundary. |

## Consequences

- **Benefit:** Multiple editor applications can use one integration and receive its current configuration without maintaining separate copies. The existing integration model and most of its infrastructure remain intact.
- **Maintenance cost:** The shared application appears in ordinary backend application queries. Application-wide features must deliberately exclude or protect it where necessary, including aggregate counts.
- **Editor availability:** Deleting a workspace integration breaks editor services that reference it, including those in duplicates and restored snapshots, until it is restored from trash; published copies remain unaffected.
- **Publishing cost:** Credential rotation across published copies requires republishing each affected app or workflow. Pushing integration changes without publishing unrelated app changes is deferred.
- **Portability cost:** Workspace imports and templates produce app-level copies rather than preserving shared ownership.
- **Security boundary:** Workspace integrations can make an authorised Local Baserow identity usable from multiple apps; Builders may select but not manage these integrations.
- **Follow-ups:** Usage counts on delete; removal of lazy creation and the backfill task once a data migration guarantees every workspace has a shared application.
- **v2 candidates:** integration-only publishing; bulk “Replace with” for services and user sources; and potentially allowing Builders to share integrations.

## Revisit triggers

- Reconsider the hidden shared application if excluding it from general application operations becomes a recurring source of defects or disproportionate maintenance work.
- Reconsider independent published copies if central credential rotation requires stronger consistency or a faster operational response than republishing can provide.
- Reconsider snapshot reference semantics if users need restored snapshots to recover historical integration settings.
- Reconsider flattened exports if preserving sharing across workspace imports becomes a core requirement.
- Reconsider Admin-only management if workspace workflows require Builders to share integrations directly.
