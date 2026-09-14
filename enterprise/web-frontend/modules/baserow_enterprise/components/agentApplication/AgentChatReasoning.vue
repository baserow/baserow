<template>
  <div
    class="agent-chat-reasoning"
    :class="{ 'agent-chat-reasoning--live': live }"
  >
    <span v-if="live" class="agent-chat-reasoning__indicator"></span>
    <!-- eslint-disable vue/no-v-html -->
    <div
      class="agent-chat-reasoning__text"
      :class="{ 'agent-chat-reasoning__text--collapsed': !live && !expanded }"
      v-html="rendered"
    ></div>
    <!-- eslint-enable vue/no-v-html -->
    <button
      v-if="!live"
      class="agent-chat-reasoning__toggle"
      @click="expanded = !expanded"
    >
      <i
        class="iconoir-nav-arrow-down agent-chat-reasoning__chevron"
        :class="{ 'agent-chat-reasoning__chevron--expanded': expanded }"
      ></i>
    </button>
  </div>
</template>

<script>
import { defineComponent, computed, ref } from 'vue'
import { renderMarkdown } from '@baserow_enterprise/utils/agentMarkdown'

export default defineComponent({
  name: 'AgentChatReasoning',
  props: {
    event: {
      type: Object,
      required: true,
    },
    live: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup(props) {
    const expanded = ref(false)
    const rendered = computed(() => renderMarkdown(props.event.content))
    return { expanded, rendered }
  },
})
</script>
