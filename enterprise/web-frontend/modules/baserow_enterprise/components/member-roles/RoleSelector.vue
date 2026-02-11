<template>
  <div>
    <span v-if="disabled">
      {{ currentValue.name }}
    </span>
    <a
      v-else
      ref="editRoleContextLink"
      @click="$refs.editRoleContext.toggle($refs.editRoleContextLink)"
    >
      {{ currentValue.name }}
      <i class="iconoir-nav-arrow-down"></i>
    </a>
    <EditRoleContext
      ref="editRoleContext"
      :subject="currentValue"
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
  emits: ['delete', 'input', 'update:modelValue'],
  components: { EditRoleContext },
  props: {
    value: {
      type: Object,
      default: undefined,
    },
    modelValue: {
      type: Object,
      default: undefined,
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
  computed: {
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value || {}
    },
  },
  methods: {
    roleUpdated({ uid }) {
      const role = this.roles.find((role) => role.uid === uid)
      this.$emit('input', role)
      this.$emit('update:modelValue', role)
    },
  },
}
</script>
