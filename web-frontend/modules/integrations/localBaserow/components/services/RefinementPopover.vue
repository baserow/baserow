<template>
  <Chips
    ref="chip"
    type="button"
    size="small"
    class="service-form__refinement-chip"
    :icon="icon"
    :active="active"
    :class="{
      'service-form__refinement-chip--active': active,
      'service-form__refinement-chip--open': open,
    }"
    @click="toggle"
  >
    <span>{{ label }}</span>
    <span v-if="count !== null" class="service-form__refinement-count">
      {{ count }}
    </span>
  </Chips>
  <Context
    ref="context"
    class="service-form__context"
    :class="contextClass"
    overflow-scroll
    max-height-if-outside-viewport
    @shown="open = true"
    @hidden="open = false"
  >
    <div class="service-form__popover-header">
      <div class="service-form__popover-title">{{ title }}</div>
      <div v-if="description" class="service-form__popover-description">
        {{ description }}
      </div>
    </div>
    <div class="service-form__popover-body">
      <slot></slot>
    </div>
  </Context>
</template>

<script setup>
/**
 * A refinement chip, like Filter or Sort, and the popover it opens.
 */
import { inject, ref } from 'vue'
import Context from '@baserow/modules/core/components/Context'

const props = defineProps({
  icon: { type: String, required: true },
  label: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  // The number shown on the chip, or `null` for none.
  count: { type: [Number, String], default: null },
  active: { type: Boolean, default: false },
  contextClass: { type: String, default: '' },
  // The popover's width, so it can open to the chip's left.
  width: { type: Number, required: true },
})

// Open below the chip, instead of to its left as in the sidebar, where there
// is no room on the right.
const refinementsBelowButtons = inject('refinementsBelowButtons', false)

const chip = ref(null)
const context = ref(null)
const open = ref(false)

function toggle() {
  if (refinementsBelowButtons) {
    context.value.toggle(chip.value.$el, 'bottom', 'left', 4, 0)
  } else {
    context.value.toggle(
      chip.value.$el,
      'bottom',
      'left',
      -32,
      -props.width - 30
    )
  }
}
</script>
