<script setup>
import { ref, useAttrs } from 'vue'
import EdgeText from './EdgeText.vue'

defineProps({
  id: String,
  path: String,
  markerEnd: String,
  markerStart: String,
  interactionWidth: {
    type: Number,
    default: 20,
  },
  label: [String, Object],
  labelX: Number,
  labelY: Number,
  labelShowBg: Boolean,
  labelBgStyle: Object,
  labelBgPadding: [Number, Array],
  labelBgBorderRadius: Number,
  labelStyle: Object,
})

const pathEl = ref(null)
const interactionEl = ref(null)
const labelEl = ref(null)

const attrs = useAttrs()

defineExpose({
  pathEl,
  interactionEl,
  labelEl,
})
</script>

<script>
export default {
  name: 'BaseEdge',
  inheritAttrs: false,
  compatConfig: { MODE: 3 },
}
</script>

<template>
  <g>
    <path
      v-bind="attrs"
      :id="id"
      ref="pathEl"
      :d="path"
      class="vue-flow__edge-path"
      :marker-end="markerEnd"
      :marker-start="markerStart"
    />

    <path
      v-if="interactionWidth"
      ref="interactionEl"
      fill="none"
      :d="path"
      :stroke-width="interactionWidth"
      :stroke-opacity="0"
      class="vue-flow__edge-interaction"
    />

    <EdgeText
      v-if="label && labelX && labelY"
      ref="labelEl"
      :x="labelX"
      :y="labelY"
      :label="label"
      :label-show-bg="labelShowBg"
      :label-bg-style="labelBgStyle"
      :label-bg-padding="labelBgPadding"
      :label-bg-border-radius="labelBgBorderRadius"
      :label-style="labelStyle"
    />
  </g>
</template>
