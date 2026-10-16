<template>
  <div class="members-role-field">
    <RoleSelectorButton
      :icon="selectedRole?.icon"
      :role-name="selectedRole?.name || ''"
      :read-only="
        userId === row.user_id ||
        !$hasPermission(
          'workspace_user.update',
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
      role-value-column="role_uid"
      @update-role="roleUpdate($event)"
    ></EditRoleContext>
    <HelpIcon
      v-if="roleUidSelected === 'NO_ACCESS'"
      :tooltip="$t('membersRoleField.noAccessHelpText')"
    />
    <HelpIcon
      v-if="roleUidSelected === 'ADMIN'"
      :tooltip="$t('membersRoleField.adminHelpText')"
      icon="warning-triangle"
    />
  </div>
</template>

<script>
import RoleSelectorButton from '@baserow/modules/core/components/settings/RoleSelectorButton'

import { mapGetters } from 'vuex'
import { clone } from '@baserow/modules/core/utils/object'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import { filterRoles } from '@baserow_enterprise/utils/roles'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'MembersRoleField',
  emits: ['refresh', 'row-update'],
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
      return this.roles.find((role) => role.uid === this.row.role_uid)
    },
    workspace() {
      return this.$store.getters['workspace/get'](
        this.column.additionalProps.workspaceId
      )
    },
    roles() {
      return this.workspace
        ? filterRoles(this.workspace._.roles, {
            scopeType: 'workspace',
            subjectType: 'auth.User',
          })
        : []
    },
    roleUidSelected() {
      return this.row[this.column.key]
    },
    ...mapGetters({ userId: 'auth/getUserId' }),
  },
  methods: {
    async roleUpdate({ uid: permissionsNew, subject: member }) {
      const oldMember = clone(member)
      const newMember = clone(member)
      newMember.role_uid = permissionsNew
      this.$emit('row-update', newMember)

      try {
        await RoleAssignmentsService(this.$client).assignRole(
          newMember.user_id,
          'auth.User',
          this.column.additionalProps.workspaceId,
          this.column.additionalProps.workspaceId,
          'workspace',
          permissionsNew
        )
        this.$emit('refresh')
      } catch (error) {
        this.$emit('row-update', oldMember)
        notifyIf(error)
      }
    },
  },
}
</script>
