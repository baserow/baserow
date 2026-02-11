<template>
  <div class="members-role-field">
    <span
      v-if="
        userId === row.user_id ||
        !$hasPermission(
          'workspace_user.update',
          row,
          column.additionalProps.workspaceId
        )
      "
    >
      {{ roleName(roles, row) }}
    </span>
    <a
      v-else
      ref="editRoleContextLink"
      @click="$refs.editRoleContext.toggle($refs.editRoleContextLink)"
    >
      {{ roleName(roles, row) }}
      <i class="iconoir-nav-arrow-down"></i>
    </a>
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
import { mapGetters } from 'vuex'
import { clone } from '@baserow/modules/core/utils/object'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import { filterRoles } from '@baserow_enterprise/utils/roles'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'MembersRoleField',
  emits: ['refresh', 'row-update'],
  components: { EditRoleContext },
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
    roleName(roles, row) {
      const role = roles.find((r) => r.uid === row.role_uid)
      return role?.name || ''
    },
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
