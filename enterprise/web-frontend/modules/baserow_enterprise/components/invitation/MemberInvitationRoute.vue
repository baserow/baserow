<template>
  <div class="share-scope">
    <Error :error="error"></Error>
    <template v-if="!fetchFailed">
      <ShareScopeInput
        ref="input"
        :workspace="workspace"
        :scope-type-name="scopeTypeName"
        :users="otherUsers"
        :teams="teams"
        :agents="agents"
        :agents-enabled="agentsEnabled"
        :assigned-keys="assignedKeys"
        :pending-emails="pendingEmails"
        :roles="assignableRoles"
        :email-role-uids="invitationRoleUids"
        :disabled="loading || adding"
        @add="add"
      />
      <CaptchaWidget
        ref="captchaWidget"
        class="margin-top-2"
        context="workspace_invitation"
        @token="onCaptchaToken"
      />
      <h3 class="share-scope__section-title">
        {{ $t('shareScope.directAccess', { type: scopeTypeName }) }}
      </h3>
      <div v-if="loading" class="loading"></div>
      <ScopeAccessList
        v-else
        :items="accessItems"
        :roles="assignableRoles"
        :scope-type-name="scopeTypeName"
        :workspace="workspace"
        @role-updated="updateItemRole"
      />
      <h3 class="share-scope__section-title">
        {{ $t('shareScope.inheritedAccess') }}
        <span class="share-scope__section-title-muted">
          {{ $t('shareScope.inherited') }}
        </span>
      </h3>
      <ScopeInheritedAccess
        :workspace="workspace"
        :scope-type-name="scopeTypeName"
      />
    </template>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'
import emailInvitations from '@baserow/modules/core/mixins/emailInvitations'
import error from '@baserow/modules/core/mixins/error'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import AgentService from '@baserow/modules/core/services/agent'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ScopeAccessList from '@baserow_enterprise/components/invitation/ScopeAccessList'
import ScopeInheritedAccess from '@baserow_enterprise/components/invitation/ScopeInheritedAccess'
import ShareScopeInput from '@baserow_enterprise/components/invitation/ShareScopeInput'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import TeamService from '@baserow_enterprise/services/team'
import { filterRoles } from '@baserow_enterprise/utils/roles'

const USER = 'auth.User'
const TEAM = 'baserow_enterprise.Team'
const AGENT = 'core.Agent'

/**
 * The share dialog of one object. One input adds existing members, teams and
 * agents with a role on the object, or invites a new person by email with a role
 * on the object only. Below it, everyone with a direct role is listed, pending
 * invitations included, followed by who else reaches the object through the
 * workspace. Members, teams and agents can be given no access on the object,
 * which takes it away from them below their workspace role; an invitation
 * can't, as there is no point in inviting someone to nothing. Agents only take part while the agents feature flag is on: they
 * are neither searched nor listed without it.
 */
export default {
  name: 'MemberInvitationRoute',
  components: {
    CaptchaWidget,
    ScopeAccessList,
    ScopeInheritedAccess,
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
  data() {
    return {
      loading: false,
      fetchFailed: false,
      adding: false,
      roleAssignments: [],
      scopedInvitations: [],
      teams: [],
      agents: [],
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
    /**
     * The roles a member, team or agent can hold on the object, no access
     * included.
     */
    assignableRoles() {
      return filterRoles(this.workspace._.roles, { scopeType: this.scopeType })
    },
    agentsEnabled() {
      return this.$featureFlagIsEnabled(FF_AGENTS)
    },
    /**
     * Everyone in the workspace but the current user, who can't give
     * themselves a role.
     */
    otherUsers() {
      return (this.workspace.users || []).filter(
        (user) => user.user_id !== this.userId
      )
    },
    /**
     * The keys of the members, teams and agents that already hold a role on
     * the object, which the picker lists as such rather than offers.
     */
    assignedKeys() {
      return this.roleAssignments.map(
        ({ subject_type: subjectType, subject }) => `${subjectType}:${subject.id}`
      )
    },
    pendingEmails() {
      return this.scopedInvitations.map(({ email }) => email)
    },
    /**
     * The rows of the direct access list: pending invitations first, then the
     * members, teams and agents with a role assignment on the object. Agent
     * rows are left out while the agents feature flag is off.
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
      const assignments = this.roleAssignments
        .filter(
          (roleAssignment) =>
            this.agentsEnabled || roleAssignment.subject_type !== AGENT
        )
        .map((roleAssignment) => {
          const subjectType = this.$registry.get(
            'subject',
            roleAssignment.subject_type
          )
          const name = subjectType.getDisplayName(roleAssignment.subject)
          const item = {
            key: `${roleAssignment.subject_type}:${roleAssignment.subject.id}`,
            kind: roleAssignment.subject_type,
            name,
            subtitle: null,
            badge: null,
            badgeColor: 'neutral',
            initials: '',
            icon: 'iconoir-user',
            color: subjectType.avatarColor,
            roleUid: roleAssignment.role,
            roles: this.assignableRoles,
            disabled: false,
            roleAssignment,
          }
          if (roleAssignment.subject_type === USER) {
            item.initials = nameAbbreviation(name)
            item.subtitle = roleAssignment.subject.email
            item.disabled = subjectType.isCurrentUser(
              roleAssignment.subject,
              this.userId
            )
          } else if (roleAssignment.subject_type === TEAM) {
            item.icon = 'iconoir-community'
            item.badge = this.$t('shareScope.teamBadge')
            item.subtitle = this.$t('shareScope.teamMembers', {
              count: roleAssignment.subject.subject_count,
            })
          } else if (roleAssignment.subject_type === AGENT) {
            item.icon = 'iconoir-sparks'
            item.badge = this.$t('shareScope.agentBadge')
          }
          return item
        })
      return [...invitations, ...assignments]
    },
  },
  async mounted() {
    this.loading = true
    try {
      await Promise.all([
        this.fetchRoleAssignments(),
        this.fetchScopedInvitations(),
        this.fetchTeams(),
        this.fetchAgents(),
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
    async fetchTeams() {
      try {
        const { data } = await TeamService(this.$client).fetchAll(
          this.workspace.id
        )
        this.teams = data
      } catch (error) {
        this.teams = []
        this.showFetchError()
      }
    },
    async fetchAgents() {
      this.agents = []
      if (
        !this.agentsEnabled ||
        !this.$hasPermission(
          'workspace.list_agents',
          this.workspace,
          this.workspace.id
        )
      ) {
        return
      }
      try {
        const { data } = await AgentService(this.$client).list(
          this.workspace.id
        )
        this.agents = data.results
      } catch (error) {
        this.agents = []
        notifyIf(error, 'agent')
      }
    },
    /**
     * Gives the picked members, teams and agents the role on the object in one
     * request, then sends one scoped invitation per picked email address. Every
     * pick leaves the input as soon as it is added, so after a failure exactly
     * what wasn't added yet is still picked.
     */
    async add(selection, roleUid) {
      this.adding = true
      this.hideError()
      const subjects = selection.filter(({ type }) => type !== 'email')
      const emails = selection.filter(({ type }) => type === 'email')

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
    updateItemRole(item, roleUid) {
      if (item.kind === 'invitation') {
        return this.updateScopedInvitationRole(item.scopedInvitation, roleUid)
      }
      return this.updateRoleAssignment(item.roleAssignment, roleUid)
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
