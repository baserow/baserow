<template>
  <p>{{ $t('agents.mcpServerPlaceholder') }}</p>
</template>

<script>
export default {
  name: 'AgentMcpServerSettings',
  props: {
    modelValue: { type: Object, required: true },
    workspace: { type: Object, required: true },
    agent: { type: Object, default: null },
    roles: { type: Array, default: () => [] },
  },
}
</script>
