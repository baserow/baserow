<template>
  <Modal ref="modal" @show="onShow" @hidden="hideError">
    <Error v-if="error.visible" :error="error"></Error>
    <Tabs
      v-else
      no-padding
      :selected-index="selectedTabIndex"
      @update:selected-index="selectedTabIndex = $event"
    >
      <Tab v-if="canManageApplication" :title="applicationTypeName">
        <MemberRolesTab
          :loading="loading"
          :workspace="workspace"
          :scope="applicationScope"
          :role-assignments="databaseRoleAssignments"
          :teams="teams"
          :agents="agents"
          scope-type="application"
          @invite-members="inviteDatabaseMembers"
          @invite-agents="inviteDatabaseAgents"
          @invite-teams="inviteDatabaseTeams"
          @role-updated="
            (ra, role) => updateRole(databaseRoleAssignments, ra, role)
          "
        />
      </Tab>
      <Tab
        v-if="table && canManageTable"
        :title="$t('memberRolesModal.memberRolesTableTabTitle')"
      >
        <MemberRolesTab
          :loading="loading"
          :workspace="workspace"
          :scope="table"
          :role-assignments="tableRoleAssignments"
          :teams="teams"
          :agents="agents"
          scope-type="database_table"
          @invite-members="inviteTableMembers"
          @invite-agents="inviteTableAgents"
          @invite-teams="inviteTableTeams"
          @role-updated="
            (ra, role) => updateRole(tableRoleAssignments, ra, role)
          "
        />
      </Tab>
      <Tab
        v-if="view && canManageView"
        :title="$t('memberRolesModal.memberRolesViewTabTitle')"
      >
        <MemberRolesTab
          :loading="loading"
          :workspace="workspace"
          :scope="view"
          :role-assignments="viewRoleAssignments"
          :teams="teams"
          :agents="agents"
          scope-type="database_view"
          @invite-members="inviteViewMembers"
          @invite-agents="inviteViewAgents"
          @invite-teams="inviteViewTeams"
          @role-updated="
            (ra, role) => updateRole(viewRoleAssignments, ra, role)
          "
        />
      </Tab>
    </Tabs>
  </Modal>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import TeamService from '@baserow_enterprise/services/team'
import AgentService from '@baserow/modules/core/services/agent'
import Modal from '@baserow/modules/core/mixins/modal'
import MemberRolesTab from '@baserow_enterprise/components/member-roles/MemberRolesTab'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'MemberRolesModal',
  components: { MemberRolesTab },
  mixins: [Modal, error],
  props: {
    application: {
      type: Object,
      required: false,
      default: null,
    },
    database: {
      type: Object,
      required: false,
      default: null,
    },
    table: {
      type: Object,
      required: false,
      default: null,
    },
    view: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      databaseRoleAssignments: [],
      tableRoleAssignments: [],
      viewRoleAssignments: [],
      selectedTabIndex: 0,
      teams: [],
      agents: [],
      loading: false,
    }
  },
  computed: {
    applicationScope() {
      return this.application || this.database
    },
    workspace() {
      return this.$store.getters['workspace/get'](
        this.applicationScope.workspace.id
      )
    },
    applicationType() {
      return this.$registry.get('application', this.applicationScope.type)
    },
    applicationTypeName() {
      return (
        this.applicationType?.getName() ||
        this.$t('memberRolesModal.memberRolesDatabaseTabTitle')
      )
    },
    canManageApplication() {
      return this.$hasPermission(
        'application.read_role',
        this.applicationScope,
        this.workspace.id
      )
    },
    canManageTable() {
      return (
        this.table &&
        this.$hasPermission(
          'database.table.read_role',
          this.table,
          this.workspace.id
        )
      )
    },
    canManageView() {
      return (
        this.view &&
        this.$hasPermission(
          'database.table.view.read_role',
          this.view,
          this.workspace.id
        )
      )
    },
  },
  methods: {
    async onShow() {
      if (this.view) {
        this.selectedTabIndex = 2
      } else if (this.table) {
        this.selectedTabIndex = 1
      }

      this.loading = true
      try {
        await Promise.all([
          this.fetchMembers(),
          this.fetchTeams(),
          this.fetchAgents(),
        ])
      } finally {
        this.loading = false
      }
    },
    async fetchMembers() {
      try {
        if (this.canManageApplication) {
          const { data: databaseRoleAssignments } =
            await RoleAssignmentsService(this.$client).getRoleAssignments(
              this.workspace.id,
              this.applicationScope.id,
              'application'
            )
          this.databaseRoleAssignments = databaseRoleAssignments
        }

        if (this.canManageTable) {
          const { data: tableRoleAssignments } = await RoleAssignmentsService(
            this.$client
          ).getRoleAssignments(
            this.workspace.id,
            this.table.id,
            'database_table'
          )
          this.tableRoleAssignments = tableRoleAssignments
        }

        if (this.canManageView) {
          const { data: viewRoleAssignments } = await RoleAssignmentsService(
            this.$client
          ).getRoleAssignments(this.workspace.id, this.view.id, 'database_view')
          this.viewRoleAssignments = viewRoleAssignments
        }
      } catch (error) {
        this.databaseRoleAssignments = []
        this.tableRoleAssignments = []
        this.viewRoleAssignments = []
        this.showError(
          this.$t('memberRolesModal.error.title'),
          this.$t('memberRolesModal.error.description')
        )
      }
    },
    async fetchTeams() {
      try {
        const { data: teams } = await TeamService(this.$client).fetchAll(
          this.workspace.id
        )
        this.teams = teams
      } catch (error) {
        this.teams = []
        this.showError(
          this.$t('memberRolesModal.error.title'),
          this.$t('memberRolesModal.error.description')
        )
      }
    },
    async fetchAgents() {
      try {
        const { data } = await AgentService(this.$client).list(
          this.workspace.id
        )
        this.agents = data.results || data
      } catch (error) {
        this.agents = []
        this.showError(
          this.$t('memberRolesModal.error.title'),
          this.$t('memberRolesModal.error.description')
        )
      }
    },
    async inviteDatabaseMembers(members, role) {
      const roleAssignments = await this.invite(
        members,
        'auth.User',
        role,
        'application',
        this.applicationScope.id
      )
      this.databaseRoleAssignments =
        this.databaseRoleAssignments.concat(roleAssignments)
    },
    async inviteDatabaseTeams(teams, role) {
      const roleAssignments = await this.invite(
        teams,
        'baserow_enterprise.Team',
        role,
        'application',
        this.applicationScope.id
      )
      this.databaseRoleAssignments =
        this.databaseRoleAssignments.concat(roleAssignments)
    },
    async inviteDatabaseAgents(agents, role) {
      const roleAssignments = await this.invite(
        agents,
        'core.Agent',
        role,
        'application',
        this.applicationScope.id
      )
      this.databaseRoleAssignments =
        this.databaseRoleAssignments.concat(roleAssignments)
    },
    async inviteTableMembers(members, role) {
      const roleAssignments = await this.invite(
        members,
        'auth.User',
        role,
        'database_table',
        this.table.id
      )
      this.tableRoleAssignments =
        this.tableRoleAssignments.concat(roleAssignments)
    },
    async inviteTableTeams(teams, role) {
      const roleAssignments = await this.invite(
        teams,
        'baserow_enterprise.Team',
        role,
        'database_table',
        this.table.id
      )
      this.tableRoleAssignments =
        this.tableRoleAssignments.concat(roleAssignments)
    },
    async inviteTableAgents(agents, role) {
      const roleAssignments = await this.invite(
        agents,
        'core.Agent',
        role,
        'database_table',
        this.table.id
      )
      this.tableRoleAssignments =
        this.tableRoleAssignments.concat(roleAssignments)
    },
    async inviteViewMembers(members, role) {
      const roleAssignments = await this.invite(
        members,
        'auth.User',
        role,
        'database_view',
        this.view.id
      )
      this.viewRoleAssignments =
        this.viewRoleAssignments.concat(roleAssignments)
    },
    async inviteViewTeams(teams, role) {
      const roleAssignments = await this.invite(
        teams,
        'baserow_enterprise.Team',
        role,
        'database_view',
        this.view.id
      )
      this.viewRoleAssignments =
        this.viewRoleAssignments.concat(roleAssignments)
    },
    async inviteViewAgents(agents, role) {
      const roleAssignments = await this.invite(
        agents,
        'core.Agent',
        role,
        'database_view',
        this.view.id
      )
      this.viewRoleAssignments =
        this.viewRoleAssignments.concat(roleAssignments)
    },
    async invite(subjects, subjectType, role, scopeType, scopeId) {
      this.loading = true

      const registeredSubjectType = this.$registry.get('subject', subjectType)
      const items = subjects.map((subject) => ({
        subject_id: registeredSubjectType.getId(subject),
        subject_type: subjectType,
        scope_id: scopeId,
        scope_type: scopeType,
        role: role.uid,
      }))

      try {
        const { data: roleAssignments } = await RoleAssignmentsService(
          this.$client
        ).assignRoleBatch(this.workspace.id, items)

        this.loading = false
        return roleAssignments
      } catch (error) {
        this.loading = false
        notifyIf(error, 'application')
        return []
      }
    },
    async updateRole(roleAssignments, roleAssignment, newRole) {
      const roleAssignmentIndex = roleAssignments.findIndex(
        ({ id }) => roleAssignment.id === id
      )

      let previousRoleAssignment = null

      if (roleAssignmentIndex !== -1) {
        previousRoleAssignment = roleAssignments[roleAssignmentIndex]
        if (newRole === null) {
          roleAssignments.splice(roleAssignmentIndex, 1)
        } else {
          // Updating the role
          roleAssignments[roleAssignmentIndex] = clone(previousRoleAssignment)
          roleAssignments[roleAssignmentIndex].role = newRole
        }
      }

      try {
        const subjectId =
          roleAssignment.subject?.id ?? roleAssignment.subject_id
        await RoleAssignmentsService(this.$client).assignRole(
          subjectId,
          roleAssignment.subject_type,
          this.workspace.id,
          roleAssignment.scope_id,
          roleAssignment.scope_type,
          newRole
        )
      } catch (error) {
        // Restore previous role
        if (roleAssignmentIndex !== -1) {
          if (newRole === null) {
            roleAssignments.splice(
              roleAssignmentIndex,
              0,
              previousRoleAssignment
            )
          } else {
            roleAssignments[roleAssignmentIndex].role =
              previousRoleAssignment.role
          }
        }
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
