<template>
  <button
    class="chips"
    :class="{ 'chips--active': active, 'chips--disabled': disabled }"
    v-on="$attrs"
  >
    <i v-if="icon" class="chips__icon" :class="icon" />
    <slot />
  </button>
</template>

<script>
export default {
  name: 'Chips',
  props: {
    active: {
      required: false,
      type: Boolean,
      default: false,
    },
    disabled: {
      required: false,
      type: Boolean,
      default: false,
    },
    icon: {
      required: false,
      type: String,
      default: '',
    },
  },
}
</script>
