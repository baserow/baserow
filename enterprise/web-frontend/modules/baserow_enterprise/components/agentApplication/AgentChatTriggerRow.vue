<template>
  <div class="agent-chat-trigger">
    <a class="agent-chat-trigger__header" @click.prevent="expanded = !expanded">
      <i class="iconoir-timer agent-chat-trigger__icon"></i>
      <span class="agent-chat-trigger__title">
        {{ $t('agentChat.startedBy', { label }) }}
      </span>
      <i
        class="iconoir-nav-arrow-right agent-chat-trigger__chevron"
        :class="{ 'agent-chat-trigger__chevron--expanded': expanded }"
      ></i>
    </a>
    <pre v-if="expanded" class="agent-chat-trigger__payload">{{ payload }}</pre>
  </div>
</template>

<script>
import { defineComponent, ref } from 'vue'

export default defineComponent({
  name: 'AgentChatTriggerRow',
  props: {
    label: {
      type: String,
      required: true,
    },
    payload: {
      type: String,
      required: true,
    },
  },
  setup() {
    const expanded = ref(false)
    return { expanded }
  },
})
</script>
