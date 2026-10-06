<template>
  <li
    class="tree__item"
    :class="{ 'tree__item--loading': application._.loading }"
  >
    <div
      class="tree__action"
      :class="{ 'tree__action--highlighted': application._.selected }"
    >
      <a class="tree__link" @click="selectAgent(application)">
        <i class="tree__icon" :class="application._.type.iconClass"></i>
        <span class="tree__link-text">{{ application.name }}</span>
      </a>
    </div>
  </li>
</template>

<script>
import { AgentApplicationType } from '@baserow_enterprise/agentApplication/applicationTypes'

export default {
  name: 'AgentTemplateSidebar',
  props: {
    application: {
      type: Object,
      required: true,
    },
    page: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
  },
  emits: ['selected', 'selected-page'],
  methods: {
    selectAgent(application) {
      this.$emit('selected', application)
      this.$emit('selected-page', {
        application: AgentApplicationType.getType(),
        value: { application },
      })
    },
  },
}
</script>
