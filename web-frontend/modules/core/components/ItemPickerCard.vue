<template>
  <button
    type="button"
    class="item-picker-card"
    :class="{
      'item-picker-card--unavailable': unavailable,
      'item-picker-card--framed': framed,
    }"
    :disabled="disabled || loading"
    :aria-disabled="disabled || loading || unavailable"
    :aria-label="name"
    :aria-busy="loading || undefined"
    @click.stop="select"
  >
    <span class="item-picker-card__image">
      <img :src="image" alt="" />
    </span>
    <span class="item-picker-card__label">
      <span v-if="loading" class="loading" />
      <template v-else>
        {{ name }}
        <i
          v-if="locked"
          class="item-picker-card__lock iconoir-lock"
          aria-hidden="true"
        />
      </template>
    </span>
    <slot />
  </button>
</template>

<script setup>
const props = defineProps({
  name: { type: String, required: true },
  image: { type: String, required: true },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  unavailable: { type: Boolean, default: false },
  locked: { type: Boolean, default: false },
  framed: { type: Boolean, default: false },
})

const emit = defineEmits(['click'])

function select(event) {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>
