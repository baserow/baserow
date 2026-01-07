<template>
  <div>
    <span v-if="disabled">
      {{ value.name }}
    </span>
    <a
      v-else
      ref="editRoleContextLink"
      @click="$refs.editRoleContext.toggle($refs.editRoleContextLink)"
    >
      {{ value.name }}
      <i class="iconoir-nav-arrow-down"></i>
    </a>
    <EditRoleContext
      ref="editRoleContext"
      :subject="value"
      :roles="roles"
      :allow-removing-role="allowRemovingRole"
      :workspace="workspace"
      role-value-column="uid"
      @update-role="roleUpdated"
      @delete="$emit('delete')"
    />
  </div>
</template>

<script>
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'

export default {
  name: 'RoleSelector',
  emits: ['delete', 'input'],
  components: { EditRoleContext },
  props: {
    value: {
      type: Object,
      default: () => ({}),
    },
    roles: {
      type: Array,
      default: () => [],
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    allowRemovingRole: {
      type: Boolean,
      default: false,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  methods: {
    roleUpdated({ uid }) {
      const role = this.roles.find((role) => role.uid === uid)
      this.$emit('input', role)
    },
  },
}
</script>
