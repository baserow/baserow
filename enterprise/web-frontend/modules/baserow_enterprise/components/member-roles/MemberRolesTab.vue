<template>
  <div>
    <div class="member-roles-tab__header">
      <h2 class="member-roles-tab__header-title">
        {{
          $t(`memberRolesTab.${translationPrefix}.title`, { name: scope.name })
        }}
      </h2>
      <div>
        <HelpIcon
          :tooltip="$t(`memberRolesTab.${translationPrefix}.headerTooltip`)"
          class="margin-right-1"
        ></HelpIcon>
        <Button
          type="secondary"
          :disabled="loading"
          :loading="loading"
          @click="loading ? null : $refs.roleAssignmentModal.show()"
          >{{ $t(`memberRolesTab.${translationPrefix}.selectMembers`) }}</Button
        >
      </div>
    </div>
    <div v-if="loading" class="loading"></div>
    <div v-else>
      <Alert type="warning">
        <template #title>{{
          $t(`memberRolesTab.${translationPrefix}.warningTitle`)
        }}</template>
        <p>{{ $t(`memberRolesTab.${translationPrefix}.warningMessage`) }}</p>
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
        :teams="teamsNotInvited"
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

export default {
  name: 'MemberRolesTab',
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
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      isSharedWithEveryone: true,
    }
  },
  computed: {
    ...mapGetters({ userId: 'auth/getUserId' }),
    scopeId() {
      return this.scope.id || null
    },
    translationPrefix() {
      switch (this.scopeType) {
        case 'database':
          return 'database'
        case 'database_table':
          return 'table'
        case 'database_view':
          return 'view'
        default:
          return 'database'
      }
    },
    descriptionText() {
      return this.isSharedWithEveryone
        ? this.$t(
            `memberRolesTab.${this.translationPrefix}.everyoneHasAccess`,
            {
              name: this.scope.name,
            }
          )
        : this.$t(`memberRolesTab.${this.translationPrefix}.onlyYouHaveAccess`)
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
  },
}
</script>
