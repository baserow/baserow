<script setup>
import { useVueFlow } from '@baserow/modules/automation/components/workflow/@vue-flow/core'
import { computed } from 'vue'
import { DefaultBgColors, DotPattern, LinePattern } from './patterns'

// Définir les variantes de fond comme constantes pour l'utiliser dans le template
const DOTS = 'dots'
const LINES = 'lines'

const props = defineProps({
  id: { type: String, default: undefined },
  variant: { type: String, default: 'dots' },
  gap: { type: [Number, Array], default: 20 },
  size: { type: Number, default: 1 },
  lineWidth: { type: Number, default: 1 },
  height: { type: Number, default: 100 },
  width: { type: Number, default: 100 },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  bgColor: { type: String, default: undefined },
  patternColor: { type: String, default: undefined },
  color: { type: String, default: undefined },
  offset: { type: [Number, Array], default: 0 },
})

const { id: vueFlowId, viewport } = useVueFlow()

const background = computed(() => {
  const zoom = viewport.value.zoom || 1
  const gapArray = Array.isArray(props.gap) ? props.gap : [props.gap, props.gap]
  const gapX = gapArray[0]
  const gapY = gapArray[1]
  const scaledGap = [gapX * zoom || 1, gapY * zoom || 1]
  const scaledSize = props.size * zoom
  const offsetArray = Array.isArray(props.offset)
    ? props.offset
    : [props.offset, props.offset]
  const offsetX = offsetArray[0]
  const offsetY = offsetArray[1]

  const scaledOffset = [
    offsetX * zoom || 1 + scaledGap[0] / 2,
    offsetY * zoom || 1 + scaledGap[1] / 2,
  ]

  return {
    scaledGap,
    offset: scaledOffset,
    size: scaledSize,
  }
})

// when there are multiple flows on a page we need to make sure that every background gets its own pattern.
const patternId = computed(
  () => `pattern-${vueFlowId}${props.id ? `-${props.id}` : ''}`
)

const patternColor = computed(
  () =>
    props.color || props.patternColor || DefaultBgColors[props.variant || DOTS]
)
</script>

<script>
export default {
  name: 'Background',
}
</script>

<template>
  <svg
    class="vue-flow__background vue-flow__container"
    :style="{
      height: `${props.height > 100 ? 100 : props.height}%`,
      width: `${props.width > 100 ? 100 : props.width}%`,
    }"
  >
    <slot :id="patternId" name="pattern-container">
      <pattern
        :id="patternId"
        :x="viewport.x % background.scaledGap[0]"
        :y="viewport.y % background.scaledGap[1]"
        :width="background.scaledGap[0]"
        :height="background.scaledGap[1]"
        :patternTransform="`translate(-${background.offset[0]},-${background.offset[1]})`"
        patternUnits="userSpaceOnUse"
      >
        <slot name="pattern">
          <template v-if="props.variant === LINES">
            <LinePattern
              :size="props.lineWidth"
              :color="patternColor"
              :dimensions="background.scaledGap"
            />
          </template>

          <template v-else-if="props.variant === DOTS">
            <DotPattern :color="patternColor" :radius="background.size / 2" />
          </template>

          <svg v-if="props.bgColor" height="100" width="100">
            <rect width="100%" height="100%" :fill="props.bgColor" />
          </svg>
        </slot>
      </pattern>
    </slot>

    <rect
      :x="props.x"
      :y="props.y"
      width="100%"
      height="100%"
      :fill="`url(#${patternId})`"
    />

    <slot :id="patternId" />
  </svg>
</template>
