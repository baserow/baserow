<template>
  <FormGroup :label="$t('agents.name')" required class="margin-bottom-2">
    <FormInput
      ref="name"
      :model-value="modelValue.name"
      required
      maxlength="160"
      @update:model-value="updateValue('name', $event)"
    />
  </FormGroup>
  <FormGroup :label="$t('agents.workspaceRole')" required>
    <WorkspaceRoleSelector
      :model-value="modelValue.role_uid"
      :workspace="workspace"
      :roles="roles"
      :show-commercial-info="false"
      @update:model-value="updateValue('role_uid', $event)"
    />
  </FormGroup>
</template>

<script>
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'

export default {
  name: 'AgentGeneralSettingsForm',
  components: { WorkspaceRoleSelector },
  props: {
    modelValue: { type: Object, required: true },
    workspace: { type: Object, required: true },
    agent: { type: Object, default: null },
    roles: { type: Array, required: true },
  },
  emits: ['update:modelValue'],
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
