<template>
  <button
    class="chips"
    :class="{
      'chips--active': active,
      'chips--disabled': disabled,
      'chips--small': size === 'small',
    }"
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
    /**
     * The size of the chips. Small is a compact pill, e.g. to pick tags.
     */
    size: {
      required: false,
      type: String,
      default: 'regular',
      validator: function (value) {
        return ['regular', 'small'].includes(value)
      },
    },
  },
}
</script>
