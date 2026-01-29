<template>
  <div v-if="roleUID" class="highest-role-field">
    {{ roleName }}
    <a
      v-if="showBillable"
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
      return this.role ? this.role.name : ''
    },
    roleIsBillable() {
      return this.role ? this.role.isBillable : false
    },
    role() {
      return this.roles.find((r) => r.uid === this.roleUID)
    },
    workspace() {
      return this.$store.getters['workspace/get'](
        this.column.additionalProps.workspaceId
      )
    },
    roles() {
      // filters out role not for Team subject and not for workspace level
      return this.workspace?._.roles || []
    },
    showBillable() {
      return this.$hasPermission(
        'workspace_user.update',
        this.row,
        this.column.additionalProps.workspaceId
      )
    },
  },
  methods: {
    capitalizeFirstLetter(string) {
      return string.charAt(0).toUpperCase() + string.slice(1)
    },
  },
}
</script>
