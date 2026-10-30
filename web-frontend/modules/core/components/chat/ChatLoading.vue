<template>
  <div class="chat-loading">
    <span
      v-if="loading"
      class="loading chat-loading__spinner"
      aria-hidden="true"
    />
    <div class="chat-loading__content">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  /** The content is still being written, so a spinner shows beside it. */
  loading: { type: Boolean, default: false },
})
</script>
