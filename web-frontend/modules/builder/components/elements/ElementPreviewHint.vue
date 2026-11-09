<template>
  <button
    v-tooltip="message"
    type="button"
    class="element-preview-hint"
    :aria-label="message"
    tooltip-position="bottom-left"
    @focus="$event.currentTarget.tooltipOpen($event)"
    @blur="$event.currentTarget.tooltipClose()"
    @keydown.esc.stop="$event.currentTarget.tooltipClose()"
    @mousedown.stop
  >
    <i class="iconoir-info-empty" aria-hidden="true" />
  </button>
</template>

<script setup>
defineProps({
  message: { type: String, required: true },
})
</script>
