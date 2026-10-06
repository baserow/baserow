<template>
  <RoleSelectorButton
    :icon="selectedRole?.icon"
    :role-name="selectedRole?.name || ''"
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
    selectedRole() {
      const permissions = this.row.permissions === 'ADMIN' ? 'ADMIN' : 'MEMBER'
      return this.column.additionalProps.roles.find(
        (role) => role.uid === permissions
      )
    },
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
