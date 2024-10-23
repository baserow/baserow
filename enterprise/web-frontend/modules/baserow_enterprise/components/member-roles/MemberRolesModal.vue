<template>
  <ModalV2 ref="modal" @show="onShow" @hidden="hideError">
    <template #header-content>
      <h2>
        {{
          $t('memberRolesTab.database.title', {
            name: database.name,
          })
        }}
      </h2>
    </template>
    <template #content>
      <Error v-if="error.visible" :error="error"></Error>
      <Tabs v-else :selected-index.sync="selectedTabIndex" no-padding>
        <Tab
          v-if="canManageDatabase"
          :title="$t('memberRolesModal.memberRolesDatabaseTabTitle')"
        >
          <MemberRolesTab
            :loading="loading"
            :workspace="workspace"
            :scope="database"
            :role-assignments="databaseRoleAssignments"
            :teams="teams"
            scope-type="application"
            @invite-members="inviteDatabaseMembers"
            @invite-teams="inviteDatabaseTeams"
            @role-updated="updateRole(databaseRoleAssignments, ...arguments)"
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
            scope-type="database_table"
            @invite-members="inviteTableMembers"
            @invite-teams="inviteTableTeams"
            @role-updated="updateRole(tableRoleAssignments, ...arguments)"
          />
        </Tab>
      </Tabs>
    </template>
    <template #footer-content>
      <Button type="secondary" @click="$refs.modal.hide()">{{
        $t('action.ok')
      }}</Button>
    </template>
  </ModalV2>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import TeamService from '@baserow_enterprise/services/team'
import modalv2 from '@baserow/modules/core/mixins/modalv2'
import MemberRolesTab from '@baserow_enterprise/components/member-roles/MemberRolesTab'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'MemberRolesModal',
  components: { MemberRolesTab },
  mixins: [modalv2, error],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      databaseRoleAssignments: [],
      tableRoleAssignments: [],
      selectedTabIndex: 0,
      teams: [],
      loading: false,
    }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    canManageDatabase() {
      return this.$hasPermission(
        'application.read_role',
        this.database,
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
  },
  methods: {
    async onShow() {
      if (this.table && this.canManageTable) {
        this.selectedTabIndex = this.canManageDatabase ? 1 : 0
      }

      this.loading = true
      try {
        await Promise.all([this.fetchMembers(), this.fetchTeams()])
      } finally {
        this.loading = false
      }
    },
    async fetchMembers() {
      try {
        if (this.canManageDatabase) {
          const { data: databaseRoleAssignments } =
            await RoleAssignmentsService(this.$client).getRoleAssignments(
              this.workspace.id,
              this.database.id,
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
      } catch (error) {
        this.databaseRoleAssignments = []
        this.tableRoleAssignments = []
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
    async inviteDatabaseMembers(members, role) {
      const roleAssignments = await this.invite(
        members,
        'auth.User',
        role,
        'application',
        this.database.id
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
        this.database.id
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
    async invite(subjects, subjectType, role, scopeType, scopeId) {
      this.loading = true

      // Different subject types store their id in different fields
      const subjectTypeToIdKeyMap = {
        'auth.User': 'user_id',
        'baserow_enterprise.Team': 'id',
      }
      const subjectTypeIdKey = subjectTypeToIdKeyMap[subjectType]
      const items = subjects.map((subject) => ({
        subject_id: subject[subjectTypeIdKey],
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

      let previousRoleAssignement = null

      if (roleAssignmentIndex !== -1) {
        previousRoleAssignement = roleAssignments[roleAssignmentIndex]
        if (newRole === null) {
          roleAssignments.splice(roleAssignmentIndex, 1)
        } else {
          // Updating the role
          this.$set(
            roleAssignments,
            roleAssignmentIndex,
            clone(previousRoleAssignement)
          )
          roleAssignments[roleAssignmentIndex].role = newRole
        }
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
        // Restore previous role
        if (roleAssignmentIndex !== -1) {
          if (newRole === null) {
            roleAssignments.splice(
              roleAssignmentIndex,
              0,
              previousRoleAssignement
            )
          } else {
            roleAssignments[roleAssignmentIndex].role =
              previousRoleAssignement.role
          }
        }
        notifyIf(error, 'application')
      }
    },
  },
}
</script>
