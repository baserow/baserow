<template>
  <div v-if="roleUID" class="highest-role-field">
    {{ roleName }}
    <a
      href="https://baserow.io/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes"
      target="_blank"
    >
      <Badge v-if="roleIsBillable" color="cyan" class="margin-left-1"
        >{{ $t('highestPaidRoleField.billable') }}
      </Badge>
    </a>
  </div>
</template>

<script>
export default {
  name: 'HighestPaidRoleField',
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
  computed: {
    roleUID() {
      return this.row[this.column.key]
    },
    roleName() {
      return this.role ? this.role.getName() : ''
    },
    roleIsBillable() {
      return this.role ? this.role.getIsBillable() : ''
    },
    role() {
      return Object.values(this.$registry.getAll('roles')).find(
        (role) => role.getUid() === this.roleUID
      )
    },
  },
}
</script>
