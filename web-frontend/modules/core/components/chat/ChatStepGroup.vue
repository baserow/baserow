<template>
  <div
    class="chat-step-group"
    :class="{ 'chat-step-group--running': status === 'running' }"
    :aria-busy="status === 'running'"
  >
    <button
      v-if="lines.length"
      class="chat-step-group__header chat-step-group__header--toggle"
      type="button"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span
        :class="
          status === 'running'
            ? 'chat-step-group__spinner'
            : statusIcons[status]
        "
        class="chat-step-group__icon"
        aria-hidden="true"
      />
      <span class="chat-step-group__title">{{ title }}</span>
      <span class="chat-step-group__status">{{
        $t(statusLabels[status])
      }}</span>
      <i
        class="chat-step-group__chevron"
        :class="expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'"
        aria-hidden="true"
      />
    </button>
    <div v-else class="chat-step-group__header">
      <span
        :class="
          status === 'running'
            ? 'chat-step-group__spinner'
            : statusIcons[status]
        "
        class="chat-step-group__icon"
        aria-hidden="true"
      />
      <span class="chat-step-group__title">{{ title }}</span>
      <span class="chat-step-group__status">{{
        $t(statusLabels[status])
      }}</span>
    </div>
    <ul v-if="lines.length && expanded" class="chat-step-group__lines">
      <li v-for="line in lines" :key="line.id" class="chat-step-group__line">
        <span>{{ line.title }}</span>
        <span class="chat-step-group__status">{{
          $t(statusLabels[line.status])
        }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  title: { type: String, required: true },
  status: { type: String, required: true },
  icon: { type: String, default: 'iconoir-tools' },
  lines: { type: Array, default: () => [] },
})

const expanded = ref(true)
const statusIcons = {
  done: 'iconoir-check-circle chat-step-group__icon--done',
  failed: 'iconoir-warning-triangle chat-step-group__icon--failed',
  stopped: 'iconoir-minus-circle chat-step-group__icon--stopped',
}
const statusLabels = {
  running: 'toolPresentation.statusRunning',
  done: 'toolPresentation.statusDone',
  failed: 'toolPresentation.statusFailed',
  stopped: 'toolPresentation.statusStopped',
}
</script>
