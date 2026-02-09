<template>
  <div ref="rootEl">
    <template v-if="isVisible">
      <slot />
    </template>
    <template v-else><slot name="placeholder">...</slot></template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const isVisible = ref(false)
const rootEl = ref(null)
let observer = null

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      // Update visibility based on intersection
      if (entries[0].isIntersecting) isVisible.value = true
    },
    { threshold: 0.1 }
  )

  if (rootEl.value) observer.observe(rootEl.value)
})

onBeforeUnmount(() => {
  if (observer && rootEl.value) observer.unobserve(rootEl.value)
})
</script>
