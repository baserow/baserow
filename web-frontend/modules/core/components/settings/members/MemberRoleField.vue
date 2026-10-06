<template>
  <RoleSelectorButton
    :role-uid="row.permissions === 'ADMIN' ? 'ADMIN' : 'MEMBER'"
    :role-name="roleName(column.additionalProps.roles, row)"
    :read-only="isReadOnly"
    @click="onClick"
  />
</template>

<script>
import RoleSelectorButton from '@baserow/modules/core/components/settings/RoleSelectorButton'

export default {
  name: 'MemberRoleField',
  components: { RoleSelectorButton },
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
  emits: ['edit-role-context'],
  computed: {
    isReadOnly() {
      const { additionalProps } = this.column
      return (
        additionalProps.userId === this.row.user_id ||
        !this.$hasPermission(
          'workspace_user.update',
          this.row,
          additionalProps.workspaceId
        )
      )
    },
  },
  methods: {
    roleName(roles, row) {
      const permissions = row.permissions === 'ADMIN' ? 'ADMIN' : 'MEMBER'
      const role = roles.find((r) => r.uid === permissions)
      return role?.name || ''
    },
    onClick(event) {
      this.$emit('edit-role-context', {
        row: this.row,
        event,
        target: event.currentTarget,
        time: Date.now(),
      })
    },
  },
}
</script>
