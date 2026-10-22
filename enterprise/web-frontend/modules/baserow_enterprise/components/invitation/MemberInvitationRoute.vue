<template>
  <div class="share-scope">
    <Error :error="error"></Error>
    <template v-if="!fetchFailed">
      <ShareScopeInput
        ref="input"
        :workspace="workspace"
        :scope-type-name="scopeTypeName"
        :subjects="pickableSubjects"
        :assigned-roles="assignedRoles"
        :pending-emails="pendingEmails"
        :inherited-admins="inheritedAdmins"
        :roles="assignableRoles"
        :email-role-uids="invitationRoleUids"
        :email-disabled-reason="emailDisabledReason"
        :disabled="loading || adding"
        @add="add"
      >
        <p v-if="emailDisabledReason" class="margin-top-1">
          {{ emailDisabledReason }}
        </p>
        <CaptchaWidget
          v-if="canInviteNewUsers"
          ref="captchaWidget"
          class="margin-top-2"
          context="workspace_invitation"
          @token="onCaptchaToken"
        />
        <h3 class="invite-list__title">
          {{ $t('shareScope.directAccess', { type: scopeTypeName }) }}
        </h3>
        <div v-if="loading" class="loading"></div>
        <ScopeAccessList
          v-else
          :items="accessItems"
          :roles="assignableRoles"
          :empty-title="$t('shareScope.emptyTitle', { type: scopeTypeName })"
          :empty-description="$t('shareScope.emptyDescription')"
          :workspace="workspace"
          @role-updated="updateItemRole"
        />
        <h3 class="invite-list__title">
          {{ $t('shareScope.inheritedAccess') }}
          <span class="invite-list__title-muted">
            {{ $t('shareScope.inherited') }}
          </span>
        </h3>
        <ScopeInheritedAccess
          v-if="!loading && effectiveAccess !== null"
          :workspace="workspace"
          :target="target"
          :target-type="targetType"
          :effective-access="effectiveAccess"
          :direct-keys="Object.keys(assignedRoles)"
          @level-roles-managed="fetchEffectiveAccess"
          @close="$emit('close')"
        />
      </ShareScopeInput>
    </template>
    <ScopeNoAccessModal ref="noAccessModal" />
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import ScopeAccessList from '@baserow/modules/core/components/invitation/ScopeAccessList'
import emailInvitations from '@baserow/modules/core/mixins/emailInvitations'
import error from '@baserow/modules/core/mixins/error'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ScopeInheritedAccess from '@baserow_enterprise/components/invitation/ScopeInheritedAccess'
import ScopeNoAccessModal from '@baserow_enterprise/components/invitation/ScopeNoAccessModal'
import ShareScopeInput from '@baserow_enterprise/components/invitation/ShareScopeInput'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import { filterRoles } from '@baserow_enterprise/utils/roles'

/**
 * The share dialog of one object. One input adds existing subjects, like
 * members, teams and agents, with a role on the object, or invites a new person
 * by email with a role on the object only. Below it, everyone with a direct
 * role is listed, pending invitations included, followed by who else reaches
 * the object through a level above it, by their effective access. Subjects can
 * be given no access on the object, which takes it away from them below their
 * workspace role; an invitation can't, as there is no point in inviting someone
 * to nothing. Only assignable subject types take part; anonymous visitors are
 * display-only.
 *
 * A user or agent who is an admin of the workspace, or holds the admin role
 * themselves on the database or table the object is in, keeps full access to
 * the object whatever role it has here. Such a row shows a locked admin role
 * with an explanation, and the picker lists them with that reason instead of
 * offering them. A team's admin role never protects its members, so it is
 * shown as any other role.
 *
 * Following a link out of the dialog, such as to the members page, emits
 * `close` so that the modal doesn't stay open over that page.
 */
export default {
  name: 'MemberInvitationRoute',
  components: {
    CaptchaWidget,
    ScopeAccessList,
    ScopeInheritedAccess,
    ScopeNoAccessModal,
    ShareScopeInput,
  },
  mixins: [error, emailInvitations],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    target: {
      type: Object,
      required: true,
    },
    targetType: {
      type: Object,
      required: true,
    },
  },
  emits: ['close'],
  data() {
    return {
      loading: false,
      fetchFailed: false,
      adding: false,
      roleAssignments: [],
      parentRoleAssignments: {},
      scopedInvitations: [],
      effectiveAccess: null,
      // Counts the effective access requests, so only the latest one applies.
      effectiveAccessRequest: 0,
      subjects: {},
    }
  },
  computed: {
    ...mapGetters({ userId: 'auth/getUserId' }),
    scope() {
      return this.target.scope
    },
    scopeType() {
      return this.target.scopeType
    },
    scopeTypeName() {
      return this.targetType
        .getScopeTypeName(this.scopeType, this.scope)
        .toLowerCase()
    },
    /**
     * The roles an invitation can grant on the object.
     */
    roles() {
      return this.targetType.getRoles(this.workspace, this.target)
    },
    invitationRoleUids() {
      return this.roles.map(({ uid }) => uid)
    },
    canInviteNewUsers() {
      return this.$hasPermission(
        'workspace.create_invitation',
        this.workspace,
        this.workspace.id
      )
    },
    emailDisabledReason() {
      return this.canInviteNewUsers
        ? null
        : this.$t('shareScope.workspaceInvitationRequired')
    },
    /**
     * The roles a member, team or agent can hold on the object, no access
     * included.
     */
    assignableRoles() {
      return filterRoles(this.workspace._.roles, { scopeType: this.scopeType })
    },
    subjectTypes() {
      return this.$registry
        .getOrderedList('subject')
        .filter((subjectType) => subjectType.isEnabled(this.workspace))
    },
    /**
     * The fetched subjects per enabled subject type, without the current user,
     * who can't give themselves a role.
     */
    pickableSubjects() {
      return Object.fromEntries(
        this.subjectTypes.map((subjectType) => [
          subjectType.type,
          (this.subjects[subjectType.type] || []).filter(
            (subject) => !subjectType.isCurrentUser(subject, this.userId)
          ),
        ])
      )
    },
    /**
     * The roles of the members, teams and agents that already hold a role on
     * the object by their key, which the picker lists as such rather than
     * offers.
     */
    assignedRoles() {
      return Object.fromEntries(
        this.roleAssignments.map(
          ({ subject_type: subjectType, subject, role }) => [
            `${subjectType}:${subject.id}`,
            role,
          ]
        )
      )
    },
    pendingEmails() {
      return this.scopedInvitations.map(({ email }) => email)
    },
    adminRole() {
      return this.workspace._.roles.find(({ uid }) => uid === 'ADMIN')
    },
    /**
     * The scopes above the object, other than the workspace, whose admins keep
     * full access to it, from the outermost in.
     */
    parentScopes() {
      const { database, table } = this.target
      const parents = []
      if (
        database &&
        ['database_table', 'database_view'].includes(this.scopeType)
      ) {
        parents.push({
          scopeType: 'application',
          scope: database,
          operation: 'application.read_role',
        })
      }
      if (table && this.scopeType === 'database_view') {
        parents.push({
          scopeType: 'database_table',
          scope: table,
          operation: 'database.table.read_role',
        })
      }
      return parents
    },
    /**
     * The users and agents whose role on the object has no effect because they
     * are an admin of a level above it, as `{ '<subject type>:<id>': '<level>' }`
     * where the level is the lower case name of the outermost such level.
     */
    inheritedAdmins() {
      const admins = {}
      for (const parent of [...this.parentScopes].reverse()) {
        const level = this.targetType
          .getScopeTypeName(parent.scopeType, parent.scope)
          .toLowerCase()
        for (const roleAssignment of this.parentRoleAssignments[
          parent.scopeType
        ] || []) {
          const subjectType = this.$registry.get(
            'subject',
            roleAssignment.subject_type
          )
          if (
            roleAssignment.role === 'ADMIN' &&
            subjectType?.holdsRolesDirectly
          ) {
            admins[subjectType.getKey(roleAssignment.subject)] = level
          }
        }
      }
      const workspaceLevel = this.$t('common.workspace').toLowerCase()
      for (const subjectType of this.subjectTypes) {
        if (!subjectType.holdsRolesDirectly) {
          continue
        }
        for (const subject of this.subjects[subjectType.type] || []) {
          if (subjectType.getWorkspaceRoleUid(subject) === 'ADMIN') {
            admins[subjectType.getKey(subject)] = workspaceLevel
          }
        }
      }
      return admins
    },
    /**
     * The rows of the direct access list: pending invitations first, then the
     * subjects with a role assignment on the object. Rows of a subject type
     * that isn't enabled are left out.
     */
    accessItems() {
      const invitations = this.scopedInvitations.map((scopedInvitation) => ({
        key: `invitation:${scopedInvitation.id}`,
        kind: 'invitation',
        name: scopedInvitation.email,
        subtitle: this.$t('shareScope.noWorkspaceRole', {
          type: this.scopeTypeName,
        }),
        badge: this.$t('shareScope.invitePending'),
        badgeColor: 'yellow',
        initials: '',
        icon: 'iconoir-mail',
        color: 'neutral',
        roleUid: scopedInvitation.role,
        roles: this.roles,
        disabled: false,
        scopedInvitation,
      }))
      const enabledTypes = this.subjectTypes.map(({ type }) => type)
      const assignments = this.roleAssignments
        .filter(({ subject_type: subjectType }) =>
          enabledTypes.includes(subjectType)
        )
        .map((roleAssignment) => {
          const { subject } = roleAssignment
          const subjectType = this.$registry.get(
            'subject',
            roleAssignment.subject_type
          )
          const key = subjectType.getKey(subject)
          const adminLevel = this.inheritedAdmins[key]
          return {
            key,
            kind: roleAssignment.subject_type,
            name: subjectType.getDisplayName(subject),
            subtitle: subjectType.getSubtitle(subject),
            badge: subjectType.getBadge(),
            badgeColor: 'neutral',
            initials: subjectType.getInitials(subject),
            icon: subjectType.iconClass,
            color: subjectType.avatarColor,
            roleUid: adminLevel ? 'ADMIN' : roleAssignment.role,
            roles: adminLevel
              ? [this.adminRole].filter(Boolean)
              : this.assignableRoles,
            disabled: subjectType.isCurrentUser(subject, this.userId),
            helpText: this.getAdminHelpText(
              subjectType,
              roleAssignment.role,
              adminLevel
            ),
            roleAssignment,
          }
        })
      return [...invitations, ...assignments]
    },
  },
  async mounted() {
    this.loading = true
    try {
      await Promise.all([
        this.fetchRoleAssignments(),
        this.fetchParentRoleAssignments(),
        this.fetchScopedInvitations(),
        this.fetchEffectiveAccess(),
        ...this.subjectTypes.map((subjectType) =>
          this.fetchSubjects(subjectType)
        ),
      ])
    } finally {
      this.loading = false
    }
  },
  methods: {
    showFetchError() {
      this.fetchFailed = true
      this.showError(
        this.$t('shareScope.error.title'),
        this.$t('shareScope.error.description')
      )
    },
    async fetchRoleAssignments() {
      try {
        const { data } = await RoleAssignmentsService(
          this.$client
        ).getRoleAssignments(this.workspace.id, this.scope.id, this.scopeType)
        this.roleAssignments = data
      } catch (error) {
        this.roleAssignments = []
        this.showFetchError()
      }
    },
    /**
     * Fetches who has access to the object and where it comes from, for the
     * summary of who reaches it through a level above. Without it the rest of
     * the dialog still works, so a failure only notifies. Every change refetches
     * it, so the response of an older request is ignored once a newer one was
     * made, whichever arrives last.
     */
    async fetchEffectiveAccess() {
      const request = ++this.effectiveAccessRequest
      try {
        const { data } = await RoleAssignmentsService(
          this.$client
        ).getEffectiveAccess(this.workspace.id, this.scope.id, this.scopeType)
        if (request === this.effectiveAccessRequest) {
          this.effectiveAccess = data
        }
      } catch (error) {
        if (request === this.effectiveAccessRequest) {
          notifyIf(error)
        }
      }
    },
    /**
     * Fetches the role assignments of the scopes above the object that the user
     * may read, to tell who is an admin there. Without them the dialog still
     * works, only those admins aren't marked, so a failure only notifies.
     */
    async fetchParentRoleAssignments() {
      const service = RoleAssignmentsService(this.$client)
      await Promise.all(
        this.parentScopes
          .filter(({ operation, scope }) =>
            this.$hasPermission(operation, scope, this.workspace.id)
          )
          .map(async ({ scopeType, scope }) => {
            try {
              const { data } = await service.getRoleAssignments(
                this.workspace.id,
                scope.id,
                scopeType
              )
              this.parentRoleAssignments[scopeType] = data
            } catch (error) {
              notifyIf(error)
            }
          })
      )
    },
    /**
     * Explains the role of an admin's row: an admin of a level above keeps full
     * access whatever their role here, and a direct admin of a database or
     * table has full access to everything inside it. Nothing for anyone else.
     */
    getAdminHelpText(subjectType, roleUid, adminLevel) {
      if (adminLevel) {
        return this.$t('shareScope.inheritedAdminHelpText', {
          type: this.scopeTypeName,
          level: adminLevel,
        })
      }
      if (
        roleUid === 'ADMIN' &&
        subjectType.holdsRolesDirectly &&
        this.scopeType !== 'database_view'
      ) {
        return this.$t('shareScope.scopeAdminHelpText', {
          type: this.scopeTypeName,
        })
      }
      return null
    },
    async fetchScopedInvitations() {
      try {
        const { data } = await RoleAssignmentsService(
          this.$client
        ).getScopedInvitations(this.workspace.id, this.scope.id, this.scopeType)
        this.scopedInvitations = data
      } catch (error) {
        this.scopedInvitations = []
        this.showFetchError()
      }
    },
    /**
     * Fetches the subjects of one type that can be given a role. Without them
     * the rest of the dialog still works, so a failure only notifies.
     */
    async fetchSubjects(subjectType) {
      try {
        this.subjects[subjectType.type] =
          await subjectType.fetchAssignableSubjects(this.workspace)
      } catch (error) {
        this.subjects[subjectType.type] = []
        notifyIf(error)
      }
    },
    /**
     * Gives the picked subjects the role on the object in one
     * request, then sends one scoped invitation per picked email address. Every
     * pick leaves the input as soon as it is added, so after a failure exactly
     * what wasn't added yet is still picked.
     */
    async add(selection, roleUid) {
      const subjects = selection.filter(({ type }) => type !== 'email')
      const emails = selection.filter(({ type }) => type === 'email')
      if (
        subjects.length > 0 &&
        roleUid === 'NO_ACCESS' &&
        !(await this.$refs.noAccessModal.ask(
          this.$t(
            'shareScope.noAccessSelectionDescription',
            { count: subjects.length, type: this.scopeTypeName },
            subjects.length
          )
        ))
      ) {
        return
      }

      this.adding = true
      this.hideError()

      try {
        if (subjects.length > 0) {
          const items = subjects.map((item) => ({
            subject_id: item.id,
            subject_type: item.type,
            scope_id: this.scope.id,
            scope_type: this.scopeType,
            role: roleUid,
          }))
          const { data: roleAssignments } = await RoleAssignmentsService(
            this.$client
          ).assignRoleBatch(this.workspace.id, items)
          this.roleAssignments = this.roleAssignments.concat(
            roleAssignments.filter(Boolean)
          )
          subjects.forEach((item) => this.$refs.input.remove(item))
          this.fetchEffectiveAccess()
        }
        await this.sendInvitations(
          emails,
          roleUid,
          (item, scopedInvitation) => {
            this.$refs.input.remove(item)
            const index = this.scopedInvitations.findIndex(
              ({ id }) => id === scopedInvitation.id
            )
            if (index === -1) {
              this.scopedInvitations.push(scopedInvitation)
            } else {
              this.scopedInvitations[index] = scopedInvitation
            }
          }
        )
        this.$refs.input.reset()
      } catch (error) {
        this.handleInvitationError(error)
      } finally {
        this.adding = false
      }
    },
    async updateItemRole(item, roleUid) {
      if (item.kind === 'invitation') {
        return this.updateScopedInvitationRole(item.scopedInvitation, roleUid)
      }
      if (
        roleUid === 'NO_ACCESS' &&
        item.roleUid !== 'NO_ACCESS' &&
        !(await this.$refs.noAccessModal.ask(
          this.$t('shareScope.noAccessDescription', {
            name: item.name,
            type: this.scopeTypeName,
          })
        ))
      ) {
        return
      }
      await this.updateRoleAssignment(item.roleAssignment, roleUid)
      this.fetchEffectiveAccess()
    },
    async updateRoleAssignment(roleAssignment, newRole) {
      const index = this.roleAssignments.findIndex(
        ({ id }) => id === roleAssignment.id
      )
      const previous = this.roleAssignments[index]

      if (newRole === null) {
        this.roleAssignments.splice(index, 1)
      } else {
        this.roleAssignments[index] = { ...previous, role: newRole }
      }

      try {
        await RoleAssignmentsService(this.$client).assignRole(
          roleAssignment.subject.id,
          roleAssignment.subject_type,
          this.workspace.id,
          roleAssignment.scope_id,
          roleAssignment.scope_type,
          newRole
        )
      } catch (error) {
        if (newRole === null) {
          this.roleAssignments.splice(index, 0, previous)
        } else {
          this.roleAssignments[index] = previous
        }
        notifyIf(error, 'application')
      }
    },
    /**
     * Changes the role a pending invitation grants on the object, or revokes it
     * when `newRole` is null. Only this object is revoked, the invitation itself
     * stays on the workspace's invites page.
     */
    async updateScopedInvitationRole(scopedInvitation, newRole) {
      const index = this.scopedInvitations.findIndex(
        ({ id }) => id === scopedInvitation.id
      )
      const previous = this.scopedInvitations[index]

      if (newRole === null) {
        this.scopedInvitations.splice(index, 1)
      } else {
        this.scopedInvitations[index] = { ...previous, role: newRole }
      }

      try {
        const service = RoleAssignmentsService(this.$client)
        if (newRole === null) {
          await service.deleteScopedInvitation(scopedInvitation.id)
        } else {
          await service.updateScopedInvitation(scopedInvitation.id, newRole)
        }
      } catch (error) {
        if (newRole === null) {
          this.scopedInvitations.splice(index, 0, previous)
        } else {
          this.scopedInvitations[index] = previous
        }
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
