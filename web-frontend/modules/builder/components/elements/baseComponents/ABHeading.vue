<template>
  <component
    :is="`h${level}`"
    class="ab-heading"
    :class="`ab-heading--h${level}`"
  >
    <slot></slot>
  </component>
</template>

<script>
/**
 * @typedef ABHeading
 */

export default {
  name: 'ABHeading',
  props: {
    /**
     * @type {number} - The level of the heading. Can be 1, 2, 3, 4, 5 or 6.
     */
    level: {
      type: Number,
      default: 1,
      validator(value) {
        return [1, 2, 3, 4, 5, 6].includes(value)
      },
    },
  },
}
</script>
