<template>
  <div
    class="chat-step-group"
    :class="{ 'chat-step-group--running': status === STEP_STATUS.RUNNING }"
    :aria-busy="status === STEP_STATUS.RUNNING"
  >
    <div class="chat-step-group__heading">
      <button
        v-if="hasDetails"
        type="button"
        class="chat-step-group__header chat-step-group__header--toggle"
        :aria-expanded="expanded"
        :aria-controls="detailsId"
        @click="expanded = !expanded"
      >
        <span
          v-if="status !== STEP_STATUS.FAILED"
          :class="headerIcon"
          class="chat-step-group__icon"
          aria-hidden="true"
        />
        <span class="chat-step-group__title">{{ title }}</span>
        <span
          v-if="status !== STEP_STATUS.FAILED"
          class="chat-step-group__status"
          :class="statusClass"
        >
          {{ stepStatusLabel({ status, changesData, partial }, $t) }}
        </span>
        <i
          class="chat-step-group__chevron"
          :class="
            expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
          "
          aria-hidden="true"
        />
      </button>
      <div v-else class="chat-step-group__header">
        <span
          v-if="status !== STEP_STATUS.FAILED"
          :class="headerIcon"
          class="chat-step-group__icon"
          aria-hidden="true"
        />
        <span class="chat-step-group__title">{{ title }}</span>
        <span
          v-if="status !== STEP_STATUS.FAILED"
          class="chat-step-group__status"
          :class="statusClass"
        >
          {{ stepStatusLabel({ status, changesData, partial }, $t) }}
        </span>
      </div>
      <ChatToolFailure
        v-if="status === STEP_STATUS.FAILED"
        :reason="failureHint || $t('toolPresentation.failureFailed')"
      />
    </div>
    <p v-if="description" class="chat-step-group__description">
      {{ description }}
    </p>
    <div v-if="links.length" class="chat-step-group__links">
      <NuxtLink v-for="link in links" :key="link.id" :to="link.to">{{
        link.label
      }}</NuxtLink>
    </div>
    <div v-if="hasDetails && expanded" :id="detailsId">
      <ul v-if="lines.length" class="chat-step-group__lines">
        <li v-for="line in lines" :key="line.id" class="chat-step-group__line">
          <span
            v-if="line.status !== STEP_STATUS.FAILED"
            :class="
              line.status === STEP_STATUS.RUNNING
                ? 'chat-step-group__spinner'
                : statusIcons[line.status]
            "
            class="chat-step-group__icon chat-step-group__line-icon"
            aria-hidden="true"
          />
          <span class="chat-step-group__line-title">{{ line.title }}</span>
          <ChatToolFailure
            v-if="line.status === STEP_STATUS.FAILED"
            :reason="line.failureHint || $t('toolPresentation.failureFailed')"
          />
          <span v-else class="chat-step-group__status">
            {{ stepStatusLabel(line, $t) }}
          </span>
        </li>
      </ul>
      <div v-if="itemErrors.length" class="chat-step-group__item-errors">
        <div class="chat-step-group__input-label">
          {{ $t('toolPresentation.itemErrors') }}
        </div>
        <ul class="chat-step-group__item-error-list">
          <li
            v-for="(error, index) in itemErrors"
            :key="index"
            class="chat-step-group__item-error"
          >
            <span v-if="error.item" class="chat-step-group__item-error-name">{{
              error.item
            }}</span>
            {{ error.message }}
          </li>
        </ul>
      </div>
      <div v-if="input" class="chat-step-group__input">
        <div class="chat-step-group__input-label">
          {{ $t('toolPresentation.input') }}
        </div>
        <ChatToolInput :input="input" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, useId } from 'vue'
import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import { stepStatusLabel } from '@baserow/modules/core/toolPresentationTypes'
import ChatToolFailure from '@baserow/modules/core/components/chat/ChatToolFailure'
import ChatToolInput from '@baserow/modules/core/components/chat/ChatToolInput'

const props = defineProps({
  title: { type: String, required: true },
  status: { type: String, required: true },
  description: { type: String, default: '' },
  links: { type: Array, default: () => [] },
  changesData: { type: Boolean, default: false },
  lines: { type: Array, default: () => [] },
  input: { type: Object, default: null },
  failureHint: { type: String, default: '' },
  itemErrors: { type: Array, default: () => [] },
})

const detailsId = useId()
// Workspace activity starts open; action inputs are available on demand.
const expanded = ref(props.lines.length > 0)
const hasDetails = computed(
  () => props.lines.length > 0 || !!props.input || props.itemErrors.length > 0
)
const partial = computed(
  () => props.status === STEP_STATUS.DONE && props.itemErrors.length > 0
)
const statusClass = computed(() => ({
  'chat-step-group__status--visible':
    (props.status === STEP_STATUS.STOPPED && props.changesData) ||
    partial.value,
}))
const statusIcons = {
  [STEP_STATUS.WAITING]: 'iconoir-clock chat-step-group__icon--waiting',
  [STEP_STATUS.DONE]: 'iconoir-check-circle chat-step-group__icon--done',
  [STEP_STATUS.REJECTED]: 'iconoir-prohibition chat-step-group__icon--rejected',
  [STEP_STATUS.STOPPED]: 'iconoir-minus-circle chat-step-group__icon--stopped',
}
const headerIcon = computed(() => {
  if (props.status === STEP_STATUS.RUNNING) return 'chat-step-group__spinner'
  if (partial.value)
    return 'iconoir-warning-circle chat-step-group__icon--partial'
  return statusIcons[props.status]
})
</script>
