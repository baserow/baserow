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
  /** The viewer's own message, shown on the right. */
  own: { type: Boolean, default: false },
})
</script>
