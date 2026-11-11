<template>
  <div>
    <RoleSelectorButton
      :icon="selectedRole?.icon"
      :role-name="selectedRole?.name || ''"
      :read-only="
        !$hasPermission(
          'enterprise.teams.team.update',
          row,
          column.additionalProps.workspaceId
        )
      "
      @click="$refs.editRoleContext.toggle($event.currentTarget)"
    />
    <EditRoleContext
      ref="editRoleContext"
      :subject="row"
      :roles="roles"
      :workspace="workspace"
      role-value-column="default_role"
      @update-role="roleUpdate($event)"
    ></EditRoleContext>
  </div>
</template>

<script>
import RoleSelectorButton from '@baserow/modules/core/components/settings/RoleSelectorButton'

import { mapGetters } from 'vuex'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import { filterRoles } from '@baserow_enterprise/utils/roles'

export default {
  name: 'TeamRoleField',
  emits: ['row-update'],
  components: { EditRoleContext, RoleSelectorButton },
  props: {
    row: {
      type: Object,
      required: true,
    },
    column: {
      type: Object,
      required: true,
    },
  },
  computed: {
    selectedRole() {
      return this.roles.find((role) => role.uid === this.row.default_role)
    },
    workspace() {
      return this.$store.getters['workspace/get'](
        this.column.additionalProps.workspaceId
      )
    },
    scopeType() {
      return this.column.additionalProps?.scopeType || 'workspace'
    },
    roles() {
      // filters out role not for Team subject and not for workspace level
      return this.workspace
        ? filterRoles(this.workspace._.roles, {
            scopeType: this.scopeType,
            subjectType: 'baserow_enterprise.Team',
          })
        : []
    },
    ...mapGetters({ userId: 'auth/getUserId' }),
  },
  methods: {
    async roleUpdate({ uid: permissionsNew, subject: team }) {
      const oldTeam = clone(team)
      const newTeam = clone(team)
      newTeam.default_role = permissionsNew
      this.$emit('row-update', newTeam)

      try {
        await RoleAssignmentsService(this.$client).assignRole(
          newTeam.id,
          'baserow_enterprise.Team',
          this.column.additionalProps.workspaceId,
          this.column.additionalProps.workspaceId,
          'workspace',
          permissionsNew
        )
      } catch (error) {
        this.$emit('row-update', oldTeam)
        notifyIf(error, 'team')
      }
    },
  },
}
</script>
