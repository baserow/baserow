<script setup>
// Définition locale de MarkerType au lieu de l'importer
const MarkerType = {
  Arrow: 'arrow',
  ArrowClosed: 'arrowclosed',
}

const props = defineProps({
  id: String,
  type: String,
  width: {
    type: Number,
    default: 12.5,
  },
  height: {
    type: Number,
    default: 12.5,
  },
  markerUnits: {
    type: String,
    default: 'strokeWidth',
  },
  orient: {
    type: String,
    default: 'auto-start-reverse',
  },
  strokeWidth: {
    type: Number,
    default: 1,
  },
  color: {
    type: String,
    default: 'none',
  },
})
</script>

<script>
export default {
  name: 'MarkerType',
  compatConfig: { MODE: 3 },
}
</script>

<template>
  <marker
    :id="props.id"
    class="vue-flow__arrowhead"
    viewBox="-10 -10 20 20"
    refX="0"
    refY="0"
    :markerWidth="`${props.width}`"
    :markerHeight="`${props.height}`"
    :markerUnits="props.markerUnits"
    :orient="props.orient"
  >
    <polyline
      v-if="props.type === MarkerType.ArrowClosed"
      :style="{
        stroke: props.color,
        fill: props.color,
        strokeWidth: props.strokeWidth,
      }"
      stroke-linecap="round"
      stroke-linejoin="round"
      points="-5,-4 0,0 -5,4 -5,-4"
    />

    <polyline
      v-if="props.type === MarkerType.Arrow"
      :style="{
        stroke: props.color,
        strokeWidth: props.strokeWidth,
      }"
      stroke-linecap="round"
      stroke-linejoin="round"
      fill="none"
      points="-5,-4 0,0 -5,4"
    />
  </marker>
</template>
