<template>
  <svg class="workflow-connector" :viewBox="viewBox" :style="svgStyle">
    <path :d="pathData" stroke="currentColor" stroke-width="2" fill="none" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  coords: {
    type: Object,
    required: true,
    validator: (value) =>
      value.startX !== undefined &&
      value.startY !== undefined &&
      value.endX !== undefined &&
      value.endY !== undefined,
  },
  radius: { type: Number, default: 10 },
})

const bounds = computed(() => {
  const minX = Math.min(props.coords.startX, props.coords.endX)
  const maxX = Math.max(props.coords.startX, props.coords.endX)
  const minY = Math.min(props.coords.startY, props.coords.endY)
  const maxY = Math.max(props.coords.startY, props.coords.endY)

  return {
    left: minX,
    top: minY,
    width: maxX - minX + 2, // +2 to add some buffer for the stroke width
    height: maxY - minY,
  }
})

const pathData = computed(() => {
  let localStartX = props.coords.startX - bounds.value.left
  const localStartY = props.coords.startY - bounds.value.top
  let localEndX = props.coords.endX - bounds.value.left
  const localEndY = props.coords.endY - bounds.value.top

  const midY = bounds.value.height / 2

  const revX = localEndX < localStartX

  const localRadius = props.radius

  if (Math.abs(localEndX - localStartX) < 5) {
    localStartX += 1
    // Let's go straight as it's a simple line.
    return `M ${localStartX},${localStartY} L ${localStartX},${localEndY}`
  }

  if (revX) {
    // We go from right to left
    localStartX -= 1
    localEndX += 2
    return `M ${localStartX},${localStartY} L ${localStartX},${
      midY + localRadius
    } Q ${localStartX},${midY} ${localStartX - localRadius},${midY} L ${
      localEndX + props.radius
    },${midY} Q ${localEndX},${midY} ${localEndX},${
      midY - localRadius
    } L ${localEndX},${localEndY}`
  }

  // We draw fro left to right
  localStartX += 2
  return `M ${localStartX},${localStartY} L ${localStartX},${
    midY + localRadius
  } Q ${localStartX},${midY} ${localStartX + localRadius},${midY} L ${
    localEndX - props.radius
  },${midY} Q ${localEndX},${midY} ${localEndX},${
    midY - localRadius
  } L ${localEndX},${localEndY}`
})

const viewBox = computed(
  () => `0 0 ${bounds.value.width} ${bounds.value.height}`
)

const svgStyle = computed(() => ({
  position: 'absolute',
  left: `${bounds.value.left}px`,
  width: `${bounds.value.width}px`,
  height: `${bounds.value.height}px`,
  pointerEvents: 'none',
}))
</script>
