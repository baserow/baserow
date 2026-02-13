<template>
  <div
    class="template__illustration"
    :class="`template__illustration--${color}`"
  >
    <div class="template__illustration-image">
      <component :is="SvgComponent" />
    </div>
  </div>
</template>

<script>
// These constant can't be in the setup script in a SFC component
export const COLORS = ['green', 'red', 'blue', 'magenta', 'purple', 'yellow']
export const TYPES = ['calendar', 'table', 'kanban', 'gallery', 'form']
</script>

<script setup>
// eslint-disable-next-line import/first
import { computed } from 'vue'

const props = defineProps({
  color: {
    type: String,
    default: 'green',
    validator: (v) => COLORS.includes(v),
  },
  type: {
    type: String,
    default: 'table',
    validator: (v) => TYPES.includes(v),
  },
})

// Auto-import all SVGs.
const modules = import.meta.glob(
  '@baserow/modules/core/assets/images/template_illustration_*.svg',
  { eager: true }
)

/**
 * Build a structured map:
 *   variants[type][color] → component
 */
function buildVariants(types, colors, files) {
  const out = {}
  for (const type of types) {
    out[type] = {}
    for (const color of colors) {
      const filename = `template_illustration_${type}_${color}.svg`

      // Find the imported module by matching its file path
      const entry = Object.entries(files).find(([key]) =>
        key.endsWith(filename)
      )

      if (!entry) {
        throw new Error(`Missing SVG file for ${filename}`)
      }

      const mod = entry[1]
      // vite-svg-loader exposes component as default export
      out[type][color] = mod.default
    }
  }
  return out
}

const variants = buildVariants(TYPES, COLORS, modules)

const SvgComponent = computed(() => variants[props.type][props.color])
</script>
