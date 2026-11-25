<template>
  <div class="chat-message" :class="{ 'chat-message--own': own }">
    <slot />
    <div v-if="$slots.actions" class="chat-message__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  /** Shown on the right: the viewer's own message, or a visitor's. */
  own: { type: Boolean, default: false },
})
</script>
