<template>
  <div>
    <div class="member-roles-tab__header">
      <h2 class="member-roles-tab__header-title">
        {{ $t('memberRolesTab.title', translationParams) }}
      </h2>
      <div>
        <HelpIcon
          :tooltip="$t('memberRolesTab.headerTooltip', translationParams)"
          class="margin-right-1"
        ></HelpIcon>
        <Button
          type="secondary"
          :disabled="loading"
          :loading="loading"
          @click="loading ? null : $refs.roleAssignmentModal.show()"
          >{{ $t('memberRolesTab.selectMembers') }}</Button
        >
      </div>
    </div>
    <div v-if="loading" class="loading"></div>
    <div v-else>
      <Alert type="warning">
        <template #title>{{ $t('memberRolesTab.warningTitle') }}</template>
        <p>
          {{ $t('memberRolesTab.warningMessage', translationParams) }}
        </p>
      </Alert>
      <MemberRolesMembersList
        :role-assignments="roleAssignments"
        :scope-type="scopeType"
        :scope-id="scopeId"
        :workspace-id="workspace.id"
        :teams="teams"
        @role-updated="
          (roleAssignment, newRole) =>
            $emit('role-updated', roleAssignment, newRole)
        "
      />
      <RoleAssignmentModal
        ref="roleAssignmentModal"
        :scope-type="scopeType"
        :users="workspaceUsersNotInvited"
        :agents="agentsNotInvited"
        :teams="teamsNotInvited"
        @invite-agents="(agents, role) => $emit('invite-agents', agents, role)"
        @invite-teams="(teams, role) => $emit('invite-teams', teams, role)"
        @invite-members="
          (members, role) => $emit('invite-members', members, role)
        "
      />
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import MemberRolesMembersList from '@baserow_enterprise/components/member-roles/MemberRolesMembersList'
import RoleAssignmentModal from '@baserow_enterprise/components/member-roles/RoleAssignmentModal'

const MEMBER_ROLE_SCOPE_CONFIG = {
  application: {
    type: 'application',
    parent: ['workspace'],
    overrides: ['workspace'],
  },
  database_table: {
    type: 'table',
    parent: ['database', 'workspace'],
    overrides: ['workspace', 'database'],
  },
  database_view: {
    type: 'view',
    parent: ['table', 'database', 'workspace'],
    overrides: ['workspace', 'database', 'table'],
  },
}

export default {
  name: 'MemberRolesTab',
  emits: ['invite-members', 'invite-agents', 'invite-teams', 'role-updated'],
  components: {
    RoleAssignmentModal,
    MemberRolesMembersList,
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    scope: {
      type: Object,
      required: true,
    },
    scopeType: {
      type: String,
      required: true,
    },
    roleAssignments: {
      type: Array,
      required: false,
      default: () => [],
    },
    teams: {
      type: Array,
      required: false,
      default: () => [],
    },
    agents: {
      type: Array,
      required: false,
      default: () => [],
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    ...mapGetters({ userId: 'auth/getUserId' }),
    scopeId() {
      return this.scope.id || null
    },
    memberRoleScope() {
      const config =
        MEMBER_ROLE_SCOPE_CONFIG[this.scopeType] ||
        MEMBER_ROLE_SCOPE_CONFIG.application

      return {
        ...config,
        type: this.scopeLabel(config.type),
        parent: this.formatScopeLabels(config.parent, 'disjunction'),
        overrides: this.formatScopeLabels(config.overrides, 'conjunction'),
      }
    },
    translationParams() {
      return {
        name: this.scope.name,
        type: this.memberRoleScope.type,
        parent: this.memberRoleScope.parent,
        overrides: this.memberRoleScope.overrides,
      }
    },
    locale() {
      return this.$i18n.locale?.value || this.$i18n.locale
    },
    userRoleAssignments() {
      return this.roleAssignments.filter(
        (roleAssignment) => roleAssignment.subject_type === 'auth.User'
      )
    },
    teamRoleAssignments() {
      return this.roleAssignments.filter(
        (roleAssignment) =>
          roleAssignment.subject_type === 'baserow_enterprise.Team'
      )
    },
    agentRoleAssignments() {
      return this.roleAssignments.filter(
        (roleAssignment) => roleAssignment.subject_type === 'core.Agent'
      )
    },
    workspaceUsers() {
      return this.workspace.users || []
    },
    workspaceUsersNotInvited() {
      const userIds = this.userRoleAssignments.map(({ subject }) => subject.id)
      return this.workspaceUsers.filter(
        ({ user_id: userId }) =>
          !userIds.includes(userId) && userId !== this.userId
      )
    },
    teamsNotInvited() {
      const teamIds = this.teamRoleAssignments.map(({ subject }) => subject.id)
      return this.teams.filter(({ id }) => !teamIds.includes(id))
    },
    agentsNotInvited() {
      const agentIds = this.agentRoleAssignments.map(
        ({ subject }) => subject.id
      )
      return this.agents.filter(({ id }) => !agentIds.includes(id))
    },
  },
  methods: {
    scopeLabel(scope) {
      let label = null

      switch (scope) {
        case 'application':
          label = this.$registry.get('application', this.scope.type).getName()
          break
        case 'table':
          label = this.$t('trashType.table')
          break
        case 'view':
          label = this.$t('trashType.view')
          break
        case 'workspace':
          label = this.$t('common.workspace')
          break
      }

      return label?.toLocaleLowerCase(this.locale) || scope
    },
    formatScopeLabels(scopes, type) {
      const labels = scopes.map((scope) => this.scopeLabel(scope))
      return new Intl.ListFormat(this.locale, {
        style: 'long',
        type,
      }).format(labels)
    },
  },
}
</script>
