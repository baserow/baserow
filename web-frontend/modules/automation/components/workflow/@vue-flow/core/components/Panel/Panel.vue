<script setup>
import { computed } from 'vue'
import { useVueFlow } from '../../composables'

const props = defineProps({
  position: {
    type: String,
    required: true,
  },
})

const { userSelectionActive } = useVueFlow()

const positionClasses = computed(() => `${props.position}`.split('-'))
</script>

<script>
export default {
  name: 'Panel',
  compatConfig: { MODE: 3 },
}
</script>

<template>
  <div
    class="vue-flow__panel"
    :class="positionClasses"
    :style="{ pointerEvents: userSelectionActive ? 'none' : 'all' }"
  >
    <slot />
  </div>
</template>
