<template>
  <span v-if="isReadOnly">
    {{ roleName(column.additionalProps.roles, row) }}
  </span>
  <a v-else class="member-role-field__link" @click.prevent="onClick">
    <span>
      {{ roleName(column.additionalProps.roles, row) }}
    </span>
    <i class="iconoir-nav-arrow-down"></i>
  </a>
</template>

<script>
export default {
  name: 'MemberRoleField',
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
