<template>
  <div
    class="chat-step-group"
    :class="{ 'chat-step-group--running': status === STEP_STATUS.RUNNING }"
    :aria-busy="status === STEP_STATUS.RUNNING"
  >
    <button
      v-if="hasDetails"
      class="chat-step-group__header chat-step-group__header--toggle"
      type="button"
      :aria-expanded="expanded"
      :aria-controls="detailsId"
      @click="expanded = !expanded"
    >
      <span
        v-tooltip:[failureTooltipOptions]="
          status === STEP_STATUS.FAILED
            ? failureHint || $t('toolPresentation.failureFailed')
            : null
        "
        :class="
          status === STEP_STATUS.RUNNING
            ? 'chat-step-group__spinner'
            : statusIcons[status]
        "
        class="chat-step-group__icon"
        tooltip-position="bottom-right"
        aria-hidden="true"
      />
      <span class="chat-step-group__title">{{ title }}</span>
      <span class="chat-step-group__status" :class="statusClass">
        {{ stepStatusText({ status, changesData, failureHint }, $t) }}
      </span>
      <i
        class="chat-step-group__chevron"
        :class="expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'"
        aria-hidden="true"
      />
    </button>
    <div v-else class="chat-step-group__header">
      <span
        v-tooltip:[failureTooltipOptions]="
          status === STEP_STATUS.FAILED
            ? failureHint || $t('toolPresentation.failureFailed')
            : null
        "
        :class="
          status === STEP_STATUS.RUNNING
            ? 'chat-step-group__spinner'
            : statusIcons[status]
        "
        class="chat-step-group__icon"
        tooltip-position="bottom-right"
        aria-hidden="true"
      />
      <span class="chat-step-group__title">{{ title }}</span>
      <span class="chat-step-group__status" :class="statusClass">
        {{ stepStatusText({ status, changesData, failureHint }, $t) }}
      </span>
    </div>
    <div v-if="hasDetails && expanded" :id="detailsId">
      <ul v-if="lines.length" class="chat-step-group__lines">
        <li v-for="line in lines" :key="line.id" class="chat-step-group__line">
          <span
            v-tooltip:[failureTooltipOptions]="
              line.status === STEP_STATUS.FAILED
                ? line.failureHint || $t('toolPresentation.failureFailed')
                : null
            "
            :class="
              line.status === STEP_STATUS.RUNNING
                ? 'chat-step-group__spinner'
                : statusIcons[line.status]
            "
            class="chat-step-group__icon chat-step-group__line-icon"
            tooltip-position="bottom-right"
            aria-hidden="true"
          />
          <span class="chat-step-group__line-title">{{ line.title }}</span>
          <span class="chat-step-group__status">
            {{ stepStatusText(line, $t) }}
          </span>
        </li>
      </ul>
      <div v-if="inputText" class="chat-step-group__input">
        <div class="chat-step-group__input-label">
          {{ $t('toolPresentation.input') }}
        </div>
        <pre
          class="chat-step-group__input-values"
          tabindex="0"
          :aria-label="$t('toolPresentation.input')"
        ><code>{{ inputText }}</code></pre>
        <p v-if="input.truncated" class="chat-step-group__input-note">
          {{ $t('toolPresentation.inputTruncated') }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, useId } from 'vue'
import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import { stepStatusText } from '@baserow/modules/core/toolPresentationTypes'

const props = defineProps({
  title: { type: String, required: true },
  status: { type: String, required: true },
  changesData: { type: Boolean, default: false },
  icon: { type: String, default: 'iconoir-tools' },
  lines: { type: Array, default: () => [] },
  input: { type: Object, default: null },
  failureHint: { type: String, default: '' },
})

const failureTooltipOptions = {
  contentClasses: [
    'tooltip__content--expandable',
    'chat-step-group__failure-tooltip',
  ],
}
const detailsId = useId()
// Workspace activity starts open; action inputs are available on demand.
const expanded = ref(props.lines.length > 0)
const inputText = computed(() => {
  const values = props.input?.values
  if (
    !values ||
    typeof values !== 'object' ||
    Array.isArray(values) ||
    !Object.keys(values).length
  ) {
    return ''
  }
  try {
    return JSON.stringify(values, null, 2)
  } catch {
    return ''
  }
})
const hasDetails = computed(() => props.lines.length > 0 || !!inputText.value)
const statusClass = computed(() => ({
  'chat-step-group__status--visible':
    props.status === STEP_STATUS.STOPPED && props.changesData,
}))
const statusIcons = {
  [STEP_STATUS.DONE]: 'iconoir-check-circle chat-step-group__icon--done',
  [STEP_STATUS.FAILED]:
    'iconoir-warning-triangle chat-step-group__icon--failed',
  [STEP_STATUS.STOPPED]: 'iconoir-minus-circle chat-step-group__icon--stopped',
}
</script>
