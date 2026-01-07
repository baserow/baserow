<template>
  <div>
    <a
      ref="editRoleContextLink"
      class="member-role-field__link"
      @click="$refs.editRoleContext.toggle($refs.editRoleContextLink)"
    >
      <span>{{ roleName(roles, rowSanitised) }}</span>
      <i class="iconoir-nav-arrow-down"></i>
    </a>
    <EditRoleContext
      ref="editRoleContext"
      :subject="rowSanitised"
      :roles="roles"
      :workspace="workspace"
      role-value-column="permissions"
      @update-role="roleUpdate($event)"
    ></EditRoleContext>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import { clone } from '@baserow/modules/core/utils/object'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'InvitationsRoleField',
  emits: ['row-update'],
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
    ...mapGetters({ userId: 'auth/getUserId' }),
    workspace() {
      return this.$store.getters['workspace/get'](
        this.column.additionalProps.workspaceId
      )
    },
    roles() {
      return this.workspace ? this.workspace._.roles : []
    },
    rowSanitised() {
      return {
        ...this.row,
        permissions: this.roles.some(
          (role) => role.uid === this.row.permissions
        )
          ? this.row.permissions
          : 'BUILDER',
      }
    },
  },
  methods: {
    roleName(roles, row) {
      const role = roles.find((r) => r.uid === row.permissions)
      return role?.name || ''
    },
    async roleUpdate({ uid: permissionsNew, subject: invitation }) {
      const oldInvitation = clone(invitation)
      const newInvitation = clone(invitation)
      newInvitation.permissions = permissionsNew
      this.$emit('row-update', newInvitation)

      try {
        await WorkspaceService(this.$client).updateInvitation(
          newInvitation.id,
          newInvitation
        )
      } catch (error) {
        this.$emit('row-update', oldInvitation)
        notifyIf(error, 'workspace')
      }
    },
  },
}
</script>
