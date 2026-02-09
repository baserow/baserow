<template>
  <div>
    <CrudTable
      ref="crudTable"
      :service="service"
      :columns="columns"
      row-id-key="id"
      @row-context="onRowContext"
      @rows-update="teamCount = $event.length"
      @edit-role-context="onEditRoleContext"
    >
      <template #title>
        {{
          $t('teamsTable.title', {
            teamCount: teamCount,
            workspaceName: workspace.name,
          })
        }}
      </template>
      <template #header-right-side>
        <Button
          v-if="
            $hasPermission(
              'enterprise.teams.create_team',
              workspace,
              workspace.id
            )
          "
          type="primary"
          size="large"
          class="margin-left-2"
          @click="$refs.createModal.show()"
        >
          {{ $t('teamsTable.createNew') }}
        </Button>
      </template>
      <template #menus="slotProps">
        <EditTeamContext
          ref="editTeamContext"
          :workspace="workspace"
          :team="focusedTeam"
          @edit="handleEditTeam"
          @deleted="slotProps.deleteRow"
        ></EditTeamContext>
      </template>
    </CrudTable>
    <CreateTeamModal
      ref="createModal"
      :workspace="workspace"
      @created="teamCreated"
    ></CreateTeamModal>
    <UpdateTeamModal
      v-if="focusedTeam"
      ref="updateModal"
      :workspace="workspace"
      :team="focusedTeam"
      @updated="teamUpdated"
    ></UpdateTeamModal>
  </div>
</template>

<script>
import CreateTeamModal from '@baserow_enterprise/components/teams/CreateTeamModal'
import UpdateTeamModal from '@baserow_enterprise/components/teams/UpdateTeamModal'
import TeamRoleField from '@baserow_enterprise/components/crudTable/fields/TeamRoleField'
import SubjectSampleField from '@baserow_enterprise/components/crudTable/fields/SubjectSampleField'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import TeamService from '@baserow_enterprise/services/team'
import { mapGetters } from 'vuex'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import EditTeamContext from '@baserow_enterprise/components/teams/EditTeamContext'

export default {
  name: 'TeamsTable',
  components: {
    CrudTable,
    EditTeamContext,
    CreateTeamModal,
    UpdateTeamModal,
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      focusedTeam: {},
      teamCount: 0,
      editRoleTeam: {},
    }
  },
  computed: {
    ...mapGetters({ userId: 'auth/getUserId' }),
    service() {
      const service = TeamService(this.$client)
      const options = {
        ...service.options,
        urlParams: { workspaceId: this.workspace.id },
      }
      return {
        ...service,
        options,
      }
    },
    roles() {
      return this.workspace._.roles
    },
    canViewEditTeamContext() {
      return (
        this.$hasPermission(
          'enterprise.teams.team.update',
          this.workspace,
          this.workspace.id
        ) ||
        this.$hasPermission(
          'enterprise.teams.team.delete',
          this.workspace,
          this.workspace.id
        )
      )
    },
    columns() {
      const columns = [
        new CrudTableColumn(
          'name',
          this.$t('teamsTable.nameColumn'),
          SimpleField,
          true,
          true
        ),
        new CrudTableColumn(
          'default_role',
          this.$t('teamsTable.roleColumn'),
          TeamRoleField,
          true,
          false,
          false,
          {
            roles: this.roles,
            workspaceId: this.workspace.id,
            scopeType: 'workspace',
          },
          this.$t('teamsTable.roleHelpText')
        ),
        new CrudTableColumn(
          'subject_sample',
          this.$t('teamsTable.subjectsColumn'),
          SubjectSampleField,
          true
        ),
      ]

      // If the user can update or delete teams, then they get an extra column for the context.
      const canUpdate = this.$hasPermission(
        'enterprise.teams.team.update',
        this.workspace,
        this.workspace.id
      )
      const canDelete = this.$hasPermission(
        'enterprise.teams.team.delete',
        this.workspace,
        this.workspace.id
      )
      if (canUpdate || canDelete) {
        columns.push(
          new CrudTableColumn(null, null, MoreField, false, false, true)
        )
      }

      return columns
    },
  },
  methods: {
    handleEditTeam(team) {
      this.focusedTeam = team
      this.$refs.updateModal.show()
    },
    onRowContext({ row, event, target }) {
      if (!this.canViewEditTeamContext) {
        // The user needs to have update or delete team
        // permissions to launch the row context.
        return
      }
      event.preventDefault()
      if (target === undefined) {
        target = {
          left: event.clientX,
          top: event.clientY,
        }
      }

      const action = row.id === this.focusedTeam.id ? 'toggle' : 'show'
      this.focusedTeam = row
      this.$refs.editTeamContext[action](target, 'bottom', 'left', 4)
    },
    onEditRoleContext({ row, target }) {
      const action = row.id === this.editRoleTeam.id ? 'toggle' : 'show'
      this.editRoleTeam = row
      this.$refs.editRoleContext[action](target, 'bottom', 'left', 4)
    },
    teamCreated(data) {
      this.$refs.crudTable.rows.push(data)
    },
    teamUpdated(data) {
      this.$refs.crudTable.updateRow(data)
    },
  },
}
</script>
