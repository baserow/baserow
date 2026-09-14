<template>
  <a class="agent-configuration-row" @click.prevent="$emit('click')">
    <span class="agent-configuration-row__icon">
      <i :class="icon"></i>
    </span>
    <span class="agent-configuration-row__body">
      <span class="agent-configuration-row__title">{{ title }}</span>
      <span v-if="summary" class="agent-configuration-row__summary">{{
        summary
      }}</span>
    </span>
    <span v-if="rightLabel" class="agent-configuration-row__right">{{
      rightLabel
    }}</span>
    <i class="iconoir-nav-arrow-right agent-configuration-row__chevron"></i>
  </a>
</template>

<script>
export default {
  name: 'AgentConfigurationSectionRow',
  props: {
    icon: {
      type: String,
      required: true,
    },
    title: {
      type: String,
      required: true,
    },
    summary: {
      type: String,
      required: false,
      default: '',
    },
    rightLabel: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['click'],
}
</script>
