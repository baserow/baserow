<template>
  <button
    class="ab-button"
    :class="{
      [`ab-button--${size}`]: true,
      [`ab-button--${textAlignment}`]: textAlignment !== 'center',
      'ab-button--full-width': fullWidth === true,
      'loading-spinner': loading,
    }"
    @click="onClick"
  >
    <span><slot></slot></span>
  </button>
</template>

<script>
/**
 * @typedef ABButton
 */

export default {
  name: 'ABButton',
  props: {
    /**
     * @type {string} - The size of the button. Can be `small`, `medium` (default) or `large`.
     */
    size: {
      type: String,
      required: false,
      default: 'medium',
      validator(value) {
        return ['small', 'medium', 'large'].includes(value)
      },
    },
    /**
     * @type {string} - Wheter the button should be full width.
     */
    fullWidth: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * @type {string} - The alignment of the button. Can be `left`, `center` (default) or `right`.
     */
    textAlignment: {
      type: String,
      required: false,
      default: 'center',
      validator(value) {
        return ['left', 'center', 'right'].includes(value)
      },
    },
    /**
     * @type {boolean} - Whether the button is in a loading state.
     */
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['click'],
  methods: {
    /**
     * @function
     * @name ABButton#onClick
     * @param {Event} event
     */
    onClick(event) {
      this.$emit('click', event)
    },
  },
}
</script>
