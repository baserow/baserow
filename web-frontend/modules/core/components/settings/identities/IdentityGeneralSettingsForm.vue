<template>
  <FormGroup :label="$t('identities.name')" required class="margin-bottom-2">
    <FormInput
      ref="name"
      :model-value="modelValue.name"
      required
      :maxlength="150"
      @update:model-value="updateValue('name', $event)"
    />
  </FormGroup>
  <FormGroup
    :label="$t('identities.workspaceRole')"
    :helper-text="canUseNoAccess ? $t('identities.roleHelpText') : null"
    required
  >
    <WorkspaceRoleSelector
      :model-value="modelValue.role_uid"
      :workspace="workspace"
      :roles="roles"
      :show-commercial-info="false"
      show-role-icons
      @update:model-value="updateValue('role_uid', $event)"
    />
  </FormGroup>
</template>

<script>
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'

export default {
  name: 'IdentityGeneralSettingsForm',
  components: { WorkspaceRoleSelector },
  props: {
    modelValue: { type: Object, required: true },
    workspace: { type: Object, required: true },
    identity: { type: Object, default: null },
    roles: { type: Array, required: true },
  },
  emits: ['update:modelValue'],
  computed: {
    canUseNoAccess() {
      return this.roles.some(
        (role) => role.uid === 'NO_ACCESS' && !role.isDeactivated
      )
    },
  },
  methods: {
    focus() {
      this.$refs.name?.focus()
    },
    updateValue(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
    },
  },
}
</script>
