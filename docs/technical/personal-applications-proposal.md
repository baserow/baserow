# Personal applications through RBAC inheritance

Proposal based on `develop` at `74d6625a49`.

Every application type offers a name and a choice of **Collaborative** or
**Personal** at creation. Collaborative is the default for existing apps and
for clients that omit the choice. A Personal application starts with one direct
application Admin grant for its creator. Anyone who directly holds the workspace
Admin role can also see and manage it, including managing its access if the
creator leaves. Other members gain access through explicit grants to themselves
or their teams. Sharing the app through the existing RBAC invitation dialog
keeps it Personal. The creation form should say “You and workspace admins can
access this app. You can invite others later.”

| Actor | Collaborative app | Personal app |
| --- | --- | --- |
| Creator with workspace Builder | Inherits Builder | Direct application Admin |
| Direct workspace Admin, even with a lower grant on the app | Admin | Admin |
| Member whose only access comes from a team's workspace Admin role | Inherits the team's role | No access |
| Member with a direct Editor grant on the app | Existing RBAC rules apply | Editor |
| Member of a team granted Viewer on the app | Existing RBAC rules apply | Viewer under the usual user/team precedence |
| Future workspace member with no applicable grant | Inherits their workspace role | No access |

### Resolve the policy in Enterprise RBAC

Store the inheritance choice once per Personal application. An Enterprise
one-to-one record referencing the base `core.Application` would make existing
applications Collaborative without a data migration. Keep the creator's Admin
grant in the existing role assignment table. Sharing and revocation then use
normal app-scoped grants. Neither operation writes a record for each excluded
workspace member. No ownership permission manager is needed.

Apply the existing direct Admin precedence throughout the workspace. For
everyone else, start with No access at a Personal app, then apply the direct
and team assignments at that scope. Below the app, keep direct application
Admin precedence and the minimum parent visibility needed to reach an
explicitly shared table or view. An app Admin acquires no new workspace
operations. [Admin precedence decision](../decisions/010-admin-role-precedence.md)

Both batch role loaders need the same rule. They build scope lists in two
directions, for many actors in a workspace and for one actor across workspaces.
Load Personal scopes in bulk, including scopes where the actor has no grant.
Keep the existing workspace Admin shortcuts for directly held Admin roles.
For actors who receive Admin through a team, account for Personal scopes
before inferring unrestricted access from a scope list containing only the
workspace entry.
Use the same result for direct requests, filtered lists, the frontend permissions
object, and the effective-access and locked-role displays. Measure both the
query count and the size of the frontend exception lists on a workspace with
many Personal databases and tables.
[Role resolution](../../enterprise/backend/src/baserow_enterprise/role/handler.py) ·
[Role permission manager](../../enterprise/backend/src/baserow_enterprise/role/permission_manager.py)

### Create and share an application

1. **Creation API.** Give core a typed, optional creation option that an
   installed plugin can validate and apply. Explicitly reject an unsupported
   option. Enterprise provides the inheritance values and enforces the RBAC
   entitlement on the server. In one transaction, create the app, record its
   policy and grant the authenticated creator Admin on the base application.
   Run the hook after the app row exists and before `init_application` creates
   children or creation events are sent. The existing `after_create` runs too
   late for this. Use the internal role handler for the initial grant, preserving
   the public API's prohibition on assigning a role to oneself. Cover callers
   outside the HTTP view, which supplies its own transaction.
   [Creation handler](../../backend/src/baserow/core/handler.py) ·
   [Application initialization](../../backend/src/baserow/core/registries.py)
2. **Creation form.** Add one generic place for plugins to contribute form
   fields and submitted values. Enterprise supplies the choice, English copy
   and lock icon. Without RBAC, activating Personal by mouse or keyboard opens
   the existing `PaidFeaturesModal` at `rbac` for that workspace and leaves
   Collaborative selected. On this base, Agent, App Builder, Automation and
   Dashboard use the shared form. Database has its own blank form and a separate
   Airtable job that derives the database name from the imported base. Carry the
   chosen name and policy through that job and apply them inside the import
   transaction. A custom creation wizard should be able to embed the same form
   extension. The separate Agent wizard branch will need that integration when
   the branches meet.
   [Creation form](../../web-frontend/modules/core/components/application/ApplicationForm.vue) ·
   [Database creation](../../web-frontend/modules/database/components/form/DatabaseForm.vue) ·
   [Airtable job](../../backend/src/baserow/contrib/database/airtable/job_types.py) ·
   [Existing RBAC modal trigger](../../enterprise/web-frontend/modules/baserow_enterprise/components/member-roles/MemberRolesApplicationContextItem.vue)
3. **Sidebar.** Return the mode with authorized application data. Support
   batched serialization for app lists and include it in the create response
   and realtime payloads. Give the shared sidebar row a generic place for an
   indicator. Enterprise renders the small icon next to the app name with an
   accessible label of “Personal application.” Keep it after invitations are
   accepted. The share dialog identifies workspace admins as always having
   access and lists the people and teams granted access.
   [Application serializers](../../backend/src/baserow/api/applications/serializers.py) ·
   [Shared sidebar row](../../web-frontend/modules/core/components/sidebar/SidebarApplication.vue)
4. **Sharing.** Reuse the application invitation target, role assignments,
   team membership and scoped email invitations. Update the dialog's inherited
   access section and role controls to reflect the boundary. A creator with
   application Admin can grant roles to existing members. Inviting an external
   email into the workspace currently also requires the workspace invitation
   permission. Supporting that for every app creator would be a separate change
   to who may admit workspace members. After a grant or revocation, refresh the
   affected client's app list as well as permissions. Today's Enterprise
   realtime handler only refetches the permissions object.
   [Scoped invitations](../../enterprise/backend/src/baserow_enterprise/role/handler.py) ·
   [Share dialog](../../enterprise/web-frontend/modules/baserow_enterprise/components/invitation/ScopeInheritedAccess.vue) ·
   [Permission refresh](../../enterprise/web-frontend/modules/baserow_enterprise/realtime.js)

### License changes, copies and rollout

- **License expiry.** Today the role manager yields to basic permissions when
  a workspace loses RBAC. Preserve access for current direct workspace admins
  and existing application grants, while gating new Personal apps and share
  management on the license. Continue resolving current membership and roles,
  including workspace Admin promotions and demotions. This requires selective
  enforcement on existing Personal scopes, including lists in a workspace
  containing both modes. Simply enabling
  all of Enterprise RBAC on expiry would change Collaborative access too.
  A build without the Enterprise plugin is a separate case. If switching a
  populated installation to OSS-only must be supported, a restriction stored
  solely in Enterprise cannot be enforced there. Decide before settling the
  schema whether to prevent that transition or persist a generic policy key in
  core that denies access when its provider is missing.
- **Workspace exports and backups.** A full workspace export requested by a
  direct workspace Admin must include every active application, whether
  Personal or Collaborative. The export job already filters applications by
  the requester's list permissions when queued and again when executed. The
  admin's existing authority supplies the complete list through both checks.
  The workspace export format omits role assignments and, for example, Agent
  conversation history. A full instance backup and restore must preserve
  application data, the Personal policy and grants together, including through
  license expiry.
  [Export selection](../../backend/src/baserow/core/job_types.py) ·
  [Workspace export configuration](../../backend/src/baserow/core/actions.py) ·
  [Agent export contents](../../backend/src/baserow/contrib/agent/application_types.py)
- **Copies and restores.** Undo/redo trashes and restores the same app. Snapshot
  restore and duplication create new app IDs. Extend the Enterprise serialization
  processor to carry the policy along with applicable grants on same-workspace
  copies. Ensure the resulting Personal copy has an active administrator. For
  imports across workspaces, the processor deliberately skips subject IDs. Offer
  a destination policy and bootstrap its creator. A private source must never
  silently become a workspace-visible copy. When the creator leaves, a direct
  workspace Admin retains access and can designate another application Admin
  while RBAC sharing is licensed.
  [Existing permission serialization](../../enterprise/backend/src/baserow_enterprise/structure_types.py)
- **Other audiences.** Workspace RBAC governs access to the application and its
  contents in the workspace. Database tokens, published Builder sites, public
  views and template copies have their own access paths. Verify that creating
  a Personal app gives no existing workspace-wide credential unintended access.
  Distinguish intentional publishing from workspace membership in the sharing
  flow. Agent conversation visibility and the identity an agent uses to run
  tools have their own semantics.
- **Release order.** Ship enforcement to every API and worker before enabling
  Personal creation. An older reader will interpret the new app as Collaborative.
  Keep creation disabled until all readers understand the policy.

### Implementation order and acceptance

1. Start with Enterprise storage and resolution. On the same app, compare a
   direct read, a list, frontend permissions and effective access for the
   creator, an uninvited workspace Admin, a team invitee and a newly joined
   member. Check that an explicit No access grant cannot lower a direct
   workspace Admin, and a team-only workspace Admin gets no automatic access.
   Include a grant limited to one child and a Collaborative sibling.
   Extend the existing [RBAC and query-count tests](../../enterprise/backend/tests/baserow_enterprise_tests/role/test_role_permission_manager.py).
2. Wire creation, licensing and lifecycle through the generic hooks. Exercise
   all five application types, the Airtable worker, rollback on a failed grant,
   duplicate, restore, and license expiry. Verify the full-workspace export
   includes both modes for a direct workspace Admin before and after expiry.
   Restore a backup and compare both application data and effective roles.
   Verify the first creation event and subsequent updates reach only authorized
   workspace users.
3. Add the Enterprise form, sidebar icon and share-dialog changes. In two
   browser sessions, create a Personal app as a workspace Builder, grant a
   member access, then revoke it. Verify sidebar visibility, direct navigation
   and an already open app after revocation. In an unlicensed workspace, verify
   the lock opens the RBAC section and Collaborative creation still succeeds.
