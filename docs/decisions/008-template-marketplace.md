# ADR 008: User Templates

|         |                                                                                      |
| ------- | ------------------------------------------------------------------------------------ |
| Status  | Proposed                                                                             |
| Date    | 2026-10-01                                                                           |
| Issue   | https://github.com/baserow/baserow/issues/1446                                       |
| Designs | https://www.figma.com/design/nI1Bt4mHkBs0T04vV6zze0/Template-marketplace?node-id=1-2 |
| Author  | Przemyslaw Kukulski (@DimmuR)                                                        |

## Problem and scope

Today every template is official: shipped in the repository and previewable by anyone.
Users have no way to share their own applications as templates. This document decides
how users turn their own applications into **user templates** that others can preview,
install and download.

In scope: the whole lifecycle of a user template within one Baserow instance, from
creation through sharing, moderation, preview, install and download to deletion.
Official templates keep working as they do today.

## Terms

| Term              | Meaning                                                                                                                                              |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Official template | Shipped in the repository. Works as today, see [Create a template](../development/create-a-template.md).                                             |
| User template     | Created by a user of this instance, who is its author.                                                                                               |
| Private / public  | Whether a user template is listed. Every user template starts private; making it public is an explicit action.                                       |
| Template link     | Permanent, non-secret address of a template.                                                                                                         |
| Private link      | Optional secret, rotatable, login-only link the author can create to share a template. Opening it grants the signed-in user access to that template. |
| Template archive  | The frozen export a user template is built from. Kept until the template is deleted or its content updated.                                          |

## Decision

A user template starts **private**, visible only to its author and instance admins.
The author can optionally create a **private link** to share it with others. **Making
it public** lists it in the "Shared templates" section, after instance admin approval
when the instance requires it.

### 1. User templates and official templates

User templates are a new concept, separate from official templates: owned by an
author, built from the author's applications and shared on their terms. The two are
managed independently and never affect each other; repository synchronization only
manages official templates. For viewers they offer the same functionality: they use the
same categories and are previewed and installed the same way.

### 2. The archive is the content

A user template's content is a signed archive in the existing export format, kept for
as long as the template uses it. Preview, install and download all derive from it.

- Creating or updating content requires export permission on the source workspace.
- The archive contains no integration credentials, no password values and no data
  identifying members of the source workspace. Ordinary cell values are kept as they
  are; the author is responsible for what they share.
- Updating content produces a new archive. The template keeps its identity and links,
  and a failed or cancelled update leaves the previous content in place.
- Archives stay installable after Baserow upgrades within the same export format major
  version. Items an instance cannot import are skipped and the rest still installs;
  this applies to workspace import too.

### 3. Preview is a rendering of the archive

Each user template gets its own hidden, memberless preview workspace imported from its
archive, the same mechanism official templates use. It can be rebuilt from the archive
at any time and is never read by install or download.

The preview is read-only and inert: viewers cannot write into it, reach it through
public views or forms, sign in as its users, or make it run the author's services. As a
result it cannot show anything that needs a signed-in app user or the author's
services, such as pages behind login or data in builder pages and dashboards; installed
copies work fully. Official template previews are unchanged.

### 4. Access

Public or private decides only whether a template is listed. Who can open it is decided
by its state, the private link and the actor's role:

| Actor                                  | Private                    | Public                     | Blocked                    |
| -------------------------------------- | -------------------------- | -------------------------- | -------------------------- |
| Anonymous                              | —                          | preview                    | —                          |
| Signed-in user                         | —                          | preview, install           | —                          |
| Signed-in user who opened private link | preview, install           | preview, install           | —                          |
| Author                                 | preview, install, manage   | preview, install, manage   | preview, delete            |
| Instance admin                         | preview, install, moderate | preview, install, moderate | preview, install, moderate |

- **Preview** covers the template's details and its preview workspace. Public templates
  also appear in the "Shared templates" section, like official templates.
- **Install** covers install and download, and always requires login.
- **Manage** is editing, sharing, making public or private, and deleting.
- **Moderate** is the instance admin actions in section 5.

Pending and rejected (section 5) count as private. Without access, a template behaves as
if it does not exist.

- Access applies to every way of reading a template: its details, preview and archive.
- A new template has no private link; the author can create, rotate or remove one.
  Access gained through it lasts until revoked.
- Rotating or removing the private link revokes access for everyone who opened it; the
  template link stays the same.
- Blocking suspends the private link and granted access; unblocking restores them.
- Rejecting disables the private link and granted access; the author cannot create a
  new one while the template is rejected.
- While the author is deactivated or pending deletion, their templates behave as
  blocked.
- Access changes take effect immediately.

### 5. Making public, approval and moderation

- **Approval** is an instance-wide setting chosen by instance admins, off by default.
  Turning it on keeps public templates public. Turning it off makes pending templates
  public; rejected ones stay private.
- **Making public** is an explicit author action. Without approval, the template becomes
  public at once. With approval, it stays pending until approved (public) or rejected
  (private, optional reason), and any edit of a public template sends it back to review.
  Making private withdraws the listing; links keep working.
- **Block** is instance admin moderation, in any state. The author can only view and
  delete a blocked template; only instance admins unblock it, back to private. Unlike
  reject, it does not invite a resubmit.
- **Abuse reports** use the existing abuse report flow.
- Authors are notified of moderation decisions; instance admins of templates awaiting
  approval.

### 6. Install and download

- Install works the same way as installing an official template.
- Download works the same way as downloading a workspace export.
- Installed copies are independent: later changes to the template never affect them.

### 7. Deletion

Deleting a template, or its author, makes it unavailable at once and removes it
permanently later; downloaded archives and installed copies are unaffected.

### 8. Other rules

- Template actions are not undoable; their effects reach beyond the actor's workspace.
  Each one that matters has an explicit inverse.
- Every template action is recorded in the audit log.
- Telemetry carries ids and states only, never a user template's name, description or
  content.
- Existing template entry points keep serving only official templates; user templates
  are reachable only under the access rules in section 4.

## Options considered

| Option                                         | Why not                                                                                                                     |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Render preview from the archive in the browser | Computed values are not exported and builder and dashboard need backend execution; weeks of work for a schema-only preview. |
| Add viewers as read-only workspace members     | Preview shows up among the user's workspaces, counts toward seats and triggers member notifications.                        |
| One link as both address and secret            | Rotating a leaked link would also change the address of a public template already shared elsewhere.                         |
| Trash with restore                             | Workspace trash does not fit memberless preview workspaces, and restore has no current need.                                |

## Consequences

- Most of the work reuses export, import, signing, the install job, the preview UI and
  usage exclusions.
- Each user template costs one archive plus a full database copy of its tables. Size and
  count limits are the lever if storage grows.
- User template previews cannot demonstrate every behavior (section 3).
- Long-lived archives create an ongoing compatibility obligation.
- Installed applications with app user logins need their users' passwords set again.

## Unresolved decisions

These questions affect user templates and are not decided yet.

| Decision                          | Question                                                                                                                                                                                                 |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Usage and billing outside Baserow | Are preview workspaces excluded from usage and billing in systems outside Baserow?                                                                                                                       |
| Public views on import            | Install keeps public views the installer did not choose to expose. Keep or reset?                                                                                                                        |
| Import report                     | How skipped items (section 2) are reported to the installer. Until then, they are logged.                                                                                                                |
| Cross-application dependencies    | Applications referencing others not included in the template keep broken references, as with workspace export today. Block, warn or accept?                                                              |
| Media cleanup                     | Media files are shared between workspaces and nothing tracks their use, so files of deleted previews stay in storage, as with deleted workspaces today. Accept, or track file usage and clean up?        |
| Template limits                   | Each template copies its rows and files, and creating or publishing one needs no approval by default. Limit templates per user, rows and file size per template? In place from the first release?        |
| Leaving rejected                  | Can the author make a rejected template private again and re-enable its private link, or only resubmit it? Either way, the author can create a new template from the same source and share it privately. |

## Technical plan

Schemas, endpoints, permission integration, background jobs, concurrency, cleanup,
migrations and rollout steps are described in a companion technical plan.
Implementation changes that keep these decisions update the plan, not this ADR.
