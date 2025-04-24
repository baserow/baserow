<script setup>
import { computed } from 'vue'
import { useVueFlow } from '../../composables'

const { viewportRef } = useVueFlow()

const teleportTarget = computed(
  () => viewportRef.value?.getElementsByClassName('vue-flow__edge-labels')[0]
)
</script>

<script>
export default {
  name: 'EdgeLabelRenderer',
  compatConfig: { MODE: 3 },
}
</script>

<template>
  <svg>
    <foreignObject height="0" width="0">
      <Teleport :to="teleportTarget" :disabled="!teleportTarget">
        <slot />
      </Teleport>
    </foreignObject>
  </svg>
</template>
