<template>
  <button
    class="button-floating"
    :class="classes"
    :disabled="disabled || loading"
    v-bind="$attrs"
  >
    <i v-if="!loading" class="button-floating__icon" :class="icon" />
  </button>
</template>

<script>
export default {
  props: {
    /**
     * The type of the button: primary or secondary
     */
    size: {
      required: false,
      type: String,
      default: 'regular',
      validator: function (value) {
        return ['small', 'regular'].includes(value)
      },
    },
    /**
     * The type of the button: primary or secondary
     */
    type: {
      required: false,
      type: String,
      default: 'primary',
      validator: function (value) {
        return ['primary', 'secondary'].includes(value)
      },
    },
    /**
     * The icon that must be shown inside the button.
     */
    icon: {
      type: String,
      default: '',
    },
    /**
     * Wether the button is loading or not.
     */
    loading: {
      required: false,
      type: Boolean,
      default: false,
    },
    disabled: {
      required: false,
      type: Boolean,
      default: false,
    },
    active: {
      required: false,
      type: Boolean,
      default: false,
    },
    position: {
      required: false,
      type: String,
      default: 'relative',
      validator: function (value) {
        return ['relative', 'fixed'].includes(value)
      },
    },
  },
  computed: {
    classes() {
      const classObj = {
        'button-floating--loading': this.loading,
        'button-floating--fixed': this.position === 'fixed',
        [`button-floating--${this.type}`]: this.type,
        [`button-floating--${this.size}`]: this.size,
        disabled: this.disabled,
        active: this.active,
      }
      return classObj
    },
  },
}
</script>
