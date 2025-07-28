<template>
  <i
    class="icon"
    :class="[icon, `icon--${type}`, `icon--${size}`]"
    v-bind="$attrs"
    v-on="$listeners"
  />
</template>

<script>
export default {
  props: {
    icon: { type: String, required: true },
    /**
     * The type of alert to display
     */
    type: {
      required: false,
      type: String,
      default: 'primary',
      validator: function (value) {
        return ['primary', 'secondary', 'warning', 'error', 'success'].includes(
          value
        )
      },
    },
    /**
     * The size
     */
    size: {
      type: String,
      required: false,
      default: 'medium',
      validator(value) {
        return ['small', 'medium', 'large', 'x-large'].includes(value)
      },
    },
  },
}
</script>
