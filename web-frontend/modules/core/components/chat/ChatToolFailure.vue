<template>
  <button
    ref="trigger"
    type="button"
    class="chat-tool-failure"
    aria-haspopup="dialog"
    :aria-expanded="context?.open ?? false"
    :aria-controls="contextId"
    @click="context.toggle($event.currentTarget, 'bottom', 'right')"
  >
    <i class="iconoir-warning-triangle" aria-hidden="true" />
    {{ $t('toolPresentation.statusFailed') }}
  </button>
  <Context
    :id="contextId"
    :key="reason"
    ref="context"
    class="context--error-message"
    role="dialog"
    tabindex="-1"
    :aria-label="$t('toolPresentation.statusFailed')"
    :aria-describedby="reasonId"
    :horizontal-viewport-margin="12"
    @shown="focusContext"
    @keydown.esc.stop="dismiss"
  >
    <p :id="reasonId" class="chat-tool-failure__reason">{{ reason }}</p>
  </Context>
</template>

<script setup>
import { nextTick, ref, useId } from 'vue'
import Context from '@baserow/modules/core/components/Context'

defineProps({ reason: { type: String, required: true } })
const trigger = ref(null)
const context = ref(null)
const contextId = useId()
const reasonId = useId()

async function focusContext() {
  await nextTick()
  if (context.value?.open) {
    context.value.getTeleportedElement().focus({ preventScroll: true })
  }
}

function dismiss() {
  context.value.hide()
  trigger.value.focus({ preventScroll: true })
}
</script>
