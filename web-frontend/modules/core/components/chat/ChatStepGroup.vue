<template>
  <div
    class="chat-step-group"
    :class="{ 'chat-step-group--running': status === STEP_STATUS.RUNNING }"
    :aria-busy="status === STEP_STATUS.RUNNING"
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
          status === STEP_STATUS.RUNNING
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
          status === STEP_STATUS.RUNNING
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
import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'

defineProps({
  title: { type: String, required: true },
  status: { type: String, required: true },
  icon: { type: String, default: 'iconoir-tools' },
  lines: { type: Array, default: () => [] },
})

const expanded = ref(true)
const statusIcons = {
  [STEP_STATUS.DONE]: 'iconoir-check-circle chat-step-group__icon--done',
  [STEP_STATUS.FAILED]:
    'iconoir-warning-triangle chat-step-group__icon--failed',
  [STEP_STATUS.STOPPED]: 'iconoir-minus-circle chat-step-group__icon--stopped',
}
const statusLabels = {
  [STEP_STATUS.RUNNING]: 'toolPresentation.statusRunning',
  [STEP_STATUS.DONE]: 'toolPresentation.statusDone',
  [STEP_STATUS.FAILED]: 'toolPresentation.statusFailed',
  [STEP_STATUS.STOPPED]: 'toolPresentation.statusStopped',
}
</script>
