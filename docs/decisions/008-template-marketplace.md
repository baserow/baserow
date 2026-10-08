# ADR 008: User Templates

|        |                                                |
| ------ | ---------------------------------------------- |
| Status | Proposed                                       |
| Date   | 2026-10-01                                     |
| Issue  | https://github.com/baserow/baserow/issues/1446 |
| Author | Przemyslaw Kukulski (@DimmuR)                  |

## Problem and scope

Today every template is official: shipped in the repository and previewable by anyone.
Users have no way to share their own applications as templates. This document decides
how users turn their own applications into **user templates** that others can preview,
install and download.

In scope: the whole lifecycle of a user template within one Baserow instance, from
creation through sharing, moderation, preview, install and download to deletion.
Official templates keep working as they do today.

## Terms

| Term               | Meaning                                                                                                                                              |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Official template  | Shipped in the repository. Works as today, see [Create a template](../development/create-a-template.md).                                             |
| User template      | Created by a user of this instance, who is its author.                                                                                               |
| Private / public   | Whether a user template is listed. Every user template starts private; making it public is an explicit action.                                       |
| Template link      | Permanent, non-secret address of a template.                                                                                                         |
| Private link       | Optional secret, rotatable, login-only link the author can create to share a template. Opening it grants the signed-in user access to that template. |
| Template workspace | Hidden, memberless workspace holding a user template's content.                                                                                      |

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

### 2. The content is a hidden workspace

A user template's content is a hidden, memberless workspace with a copy of the selected
applications, made like a snapshot but following the content rules below. It is the same
kind of workspace as an installed official template, marked as a user template so
repository synchronization and official template entry points ignore it. Preview reads
it, install copies from it, and download exports it.

- Creating or updating content requires export permission on the source workspace,
  since the copy includes every table of the selected applications.
- The copy follows the content rules below. Before creating or updating content, the
  author is told which kinds of data the copy removes and that everything else is shared
  as it is.
- Updating content replaces the copy. The template keeps its identity and links, and a
  failed or cancelled update leaves the previous content in place.
- The template workspace is migrated like every other workspace, so installs always
  start from current data.
- A template workspace does not count toward the usage of any workspace, like an
  installed official template.

The copy keeps the author's content, and only content of the source workspace, but
nothing that grants access, identifies people
of the source workspace, or stays connected to the author's resources, and nothing in it
runs. These rules apply to everything read from a template: preview, install and
download. Data added to Baserow later follows the same rules.

| Data                            | Examples                                                                                                                                                                    | Decision                                                                                                                                                                                                                       |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Integration credentials         | SMTP password, AI provider key, Slack token                                                                                                                                 | Removed                                                                                                                                                                                                                        |
| Secrets in service settings     | HTTP request and response headers, query parameters and body                                                                                                                | Removed. Request and link URLs are handled as in a workspace export                                                                                                                                                            |
| Login provider secrets          | Builder OIDC client secret, SAML identity provider metadata                                                                                                                 | Removed                                                                                                                                                                                                                        |
| Data sync connections           | Postgres host and user, Jira URL and username, iCal URL, last sync error                                                                                                    | Connection settings and credentials removed. Tables stay data syncs with their last synced rows; scheduled and two-way sync are off until the installer connects them. A sync from a table in the template needs no connection |
| Trigger addresses               | HTTP trigger URL, inbound email address                                                                                                                                     | Kept, with a new address in the template and in every installed copy; the author's addresses never appear in the template                                                                                                      |
| Test run data                   | Recorded webhook bodies and API responses                                                                                                                                   | Removed                                                                                                                                                                                                                        |
| Passwords                       | Password field cells, builder app users' passwords                                                                                                                          | Removed                                                                                                                                                                                                                        |
| People of the source workspace  | Created by and last modified by, collaborators, view owners, user filters and conditions, mentions, role assignments, notification recipients, the user AI fields update as | Removed. Personal views are not copied                                                                                                                                                                                         |
| Who services run as             | The integration user or agent of data sources, workflows and data syncs                                                                                                     | Nobody in the template; the installer in an installed copy                                                                                                                                                                     |
| References outside the template | A builder page, dashboard, button or data sync pointing to an application not included                                                                                      | Cleared                                                                                                                                                                                                                        |
| Shared views and forms          | Public grid view, form, password-protected view                                                                                                                             | Not shared, in the template or installed copies, as when duplicating a view                                                                                                                                                    |
| Running services                | Active workflows, periodic triggers                                                                                                                                         | Never run in the template; installed copies start stopped                                                                                                                                                                      |
| Files                           | Images, attachments                                                                                                                                                         | Kept, as copies that belong to the template and are deleted with it. A file link someone already opened keeps working until then                                                                                               |
| Active content                  | IFrame embedded HTML                                                                                                                                                        | Kept. Never runs with Baserow's origin in the preview; in installed copies it is off, like custom code, until the installer turns it on                                                                                        |
| Custom code                     | Builder custom JavaScript, CSS and external scripts, server-side code                                                                                                       | Kept. Never runs in the preview; off in installed copies until the installer turns it on                                                                                                                                       |
| Cell values and other content   | Rows, names, descriptions, request URLs, code, form redirect URLs, logos                                                                                                    | Kept as is; the author is responsible for what they share                                                                                                                                                                      |

### 3. Preview reads the template workspace

As for official templates, the preview reads the template workspace, for users with
access to the template.

The preview is read-only and inert: viewers cannot write into it, reach it through
public views or forms, sign in as its users, or make it run the author's services. As a
result it cannot show anything that needs a signed-in app user or the author's
services, such as pages behind login or data in builder pages and dashboards; installed
copies work fully. Official template previews are unchanged.

### 4. Access

Public or private decides only whether a template is listed. Who can open it is decided
by its state, the private link and the actor's role:

| Actor                                  | Private                    | Public                     | Blocked                                                       |
| -------------------------------------- | -------------------------- | -------------------------- | ------------------------------------------------------------- |
| Anonymous                              | —                          | preview                    | —                                                             |
| Signed-in user                         | —                          | preview, install           | —                                                             |
| Signed-in user who opened private link | preview, install           | preview, install           | —                                                             |
| Author                                 | preview, install, manage   | preview, install, manage   | preview, change details or content, submit for review, delete |
| Instance admin                         | preview, install, moderate | preview, install, moderate | preview, install, moderate                                    |

- **Preview** covers the template's details and its template workspace. Public templates
  also appear in the "Shared templates" section, like official templates.
- **Install** also covers download, and always requires login.
- **Manage** is editing details and content; creating, rotating or removing the private
  link; making public or private; and deleting.
- **Moderate** is the instance admin actions in section 5 and deleting.

Pending and rejected (section 5) count as private. Without access, a template behaves as
if it does not exist.

- Access applies to every way of reading a template: its details, preview and download.
  Being a template grants no access to its workspace by itself.
- A new template has no private link; the author can create, rotate or remove one.
  Access gained through it lasts until revoked.
- Rotating or removing the private link revokes access for everyone who opened it; the
  template link stays the same.
- Blocking suspends the private link and granted access; leaving block restores them.
- Deactivating the author or scheduling their account deletion does not change their
  templates; deleting the author deletes them (section 7).
- Access changes take effect immediately.

### 5. Making public, approval and moderation

- **Approval** is an instance-wide setting chosen by instance admins, on by default.
- **Making public** is an explicit author action, in which the author accepts that the
  template and their name are listed for everyone on the instance. If the instance does
  not require approval, the template becomes public at once.
- **If the instance requires approval**, the template stays pending until an instance
  admin approves it (public) or rejects it (private, with a reason). Any edit of a public
  template sends it back to review; an approval covers only what the admin reviewed. The
  author can resubmit a rejected template, and an instance admin can still approve it.
- **Reject** of a public template is available to instance admins whether or not the
  instance requires approval, to take it out of the listing.
- **Making private** withdraws the listing; the private link keeps working.
- **Block** is instance admin moderation, in any state, with a reason. The author can
  view and delete a blocked template, change its details or content, and submit it for
  review. A blocked template leaves block only through review, whether or not the
  instance requires approval: an instance admin approves the submitted content and
  details, or the current ones directly, which returns the template to the state it had
  before (pending becomes public), or keeps it blocked. Any edit withdraws a submission.
  Unlike reject, block also suspends the private link.
- **Abuse reports** use the existing abuse report flow.

### 6. Install and download

- Install works the same way as installing an official template, and the installed copy
  follows section 2.
- Download works the same way as downloading a workspace export: a signed archive that
  another instance can import.
- Installed copies are independent: later changes to the template never affect them.

### 7. Deletion

Deleting a template, or its author, makes it unavailable at once and removes it
permanently later; downloaded archives and installed copies are unaffected.

## Options considered

| Option                                       | Why not                                                                                                                     |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Render preview from an export in the browser | Computed values are not exported and builder and dashboard need backend execution; weeks of work for a schema-only preview. |
| Add viewers as read-only workspace members   | Preview shows up among the user's workspaces, counts toward seats and triggers member notifications.                        |
| One link as both address and secret          | Rotating a leaked link would also change the address of a public template already shared elsewhere.                         |
| Store an export archive as the content       | Not migrated with workspaces, so installs start from an outdated copy; needs version-tolerant import.                       |
| Let the author choose what the copy keeps    | Installers could no longer rely on section 2, and import would need to know what was kept on purpose.                       |
| Trash with restore                           | Workspace trash does not fit memberless template workspaces, and restore has no current need.                               |

## Consequences

- Each user template costs a full copy of its tables and files. There are no size or
  count limits; instance admins can delete templates, and limits are the lever if
  storage grows.
- User template previews cannot demonstrate every behavior (section 3).
- Installed copies need their credentials, request secrets, data sync connections and
  app user passwords set again, and their custom code and embedded HTML turned on.
