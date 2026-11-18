<template>
  <p>{{ $t('identities.mcpServerPlaceholder') }}</p>
</template>

<script>
export default {
  name: 'IdentityMcpServerSettings',
  props: {
    modelValue: { type: Object, required: true },
    workspace: { type: Object, required: true },
    identity: { type: Object, default: null },
    roles: { type: Array, default: () => [] },
  },
}
</script>
