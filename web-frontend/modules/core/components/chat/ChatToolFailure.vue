<template>
  <button
    :key="reason"
    v-tooltip:[tooltipOptions]="reason"
    type="button"
    class="chat-tool-failure"
    :aria-description="reason"
    tooltip-position="auto"
    @click.stop="$event.currentTarget.tooltipOpen($event)"
    @keydown.esc.stop="$event.currentTarget.tooltipClose()"
  >
    <i class="iconoir-warning-triangle" aria-hidden="true" />
    {{ $t('toolPresentation.statusFailed') }}
  </button>
</template>

<script setup>
import vTooltip from '@baserow/modules/core/directives/tooltip'

defineProps({ reason: { type: String, required: true } })
const tooltipOptions = {
  showOnFocus: true,
  duration: 0.2,
  contentClasses: [
    'tooltip__content--expandable',
    'tooltip__content--expandable-plain-text',
    'chat-tool-failure__tooltip',
  ],
}
</script>
