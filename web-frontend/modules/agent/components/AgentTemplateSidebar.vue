<template>
  <li class="tree__item">
    <div
      class="tree__action"
      :class="{ 'tree__action--highlighted': application._.selected }"
    >
      <a class="tree__link" @click="select">
        <i class="tree__icon" :class="application._.type.iconClass"></i>
        <span class="tree__link-text">{{ application.name }}</span>
      </a>
    </div>
  </li>
</template>

<script setup>
import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'

/** Lists an Agent in the sidebar of a template preview. */
const props = defineProps({
  application: { type: Object, required: true },
  page: {
    required: true,
    validator: (prop) => typeof prop === 'object' || prop === null,
  },
})
const emit = defineEmits(['selected', 'selected-page'])

function select() {
  emit('selected', props.application)
  emit('selected-page', {
    application: AGENT_APPLICATION_TYPE,
    value: { agent: props.application },
  })
}
</script>
