<template>
  <div class="agent-configuration__page">
    <div class="agent-configuration__header">
      <a
        v-if="showBack"
        class="agent-configuration__back"
        :title="$t('agentConfiguration.back')"
        @click="$emit('back')"
      >
        <i class="iconoir-nav-arrow-left"></i>
      </a>
      <div class="agent-configuration__title">{{ title }}</div>
      <a
        class="agent-configuration__close"
        :title="$t('agentConfiguration.close')"
        @click="$emit('close')"
      >
        <i class="iconoir-cancel"></i>
      </a>
    </div>
    <div class="agent-configuration__body">
      <slot></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AgentConfigurationSubpage',
  props: {
    title: {
      type: String,
      required: true,
    },
    showBack: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['back', 'close'],
}
</script>
