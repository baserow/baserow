<template>
  <g>
    <defs>
      <linearGradient
        :id="lightToDarkGradientId"
        gradientUnits="userSpaceOnUse"
        :x1="sourceX"
        :y1="sourceY"
        :x2="targetX"
        :y2="targetY"
      >
        <stop offset="0%" stop-color="#f7f7f7" />
        <stop offset="100%" stop-color="#e6e7e9" />
      </linearGradient>

      <linearGradient
        :id="darkToLightGradientId"
        gradientUnits="userSpaceOnUse"
        :x1="sourceX"
        :y1="sourceY"
        :x2="targetX"
        :y2="targetY"
      >
        <stop offset="0%" stop-color="#e6e7e9" />
        <stop offset="100%" stop-color="#f7f7f7" />
      </linearGradient>
    </defs>
    <path :d="path" :stroke="`url(#${activeGradientId})`" stroke-width="2" />
  </g>
</template>

<script setup>
import { getBezierPath } from '@vue2-flow/core'
import { computed } from 'vue'

const Position = {
  Top: 'top',
  Right: 'right',
  Bottom: 'bottom',
  Left: 'left',
}

const props = defineProps({
  id: {
    type: String,
    default: () => `edge-${Math.random().toString(36).substring(2, 9)}`,
  },
  sourceX: { type: Number, required: true },
  sourceY: { type: Number, required: true },
  targetX: { type: Number, required: true },
  targetY: { type: Number, required: true },
  sourcePosition: { type: String, default: 'bottom' },
  targetPosition: { type: String, default: 'top' },
})

const lightToDarkGradientId = computed(() => `edge-gradient-${props.id}`)
const darkToLightGradientId = computed(() => `edge-gradient2-${props.id}`)

const useSecondGradient = computed(() => {
  // Convert the ID to a number and check if it's odd or even
  const idNumber = parseInt(props.id.replace(/\D/g, ''), 10)
  return !isNaN(idNumber) && idNumber % 2 === 1
})

const activeGradientId = computed(() =>
  useSecondGradient.value
    ? darkToLightGradientId.value
    : lightToDarkGradientId.value
)

const path = computed(() => {
  const [pathValue] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition || Position.Bottom,
    targetPosition: props.targetPosition || Position.Top,
  })
  return pathValue
})
</script>
