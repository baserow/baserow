<template>
  <div
    class="badge-counter"
    :class="{ 'badge-counter--one-digit': hasOneDigitOnly }"
  >
    {{ value }}
  </div>
</template>

<script>
export default {
  name: 'BadgeCounter',
  props: {
    /**
     * The number to display in the badge
     */
    count: {
      type: Number,
      default: 1,
    },
    /**
     * The maximum number to display in the badge.
     * If the count value is higher the badge will display the limit value minus one with a plus sign.
     */
    limit: {
      type: Number,
      required: false,
      default: 10,
    },
  },
  computed: {
    value() {
      if (this.count > 1 && this.limit > 1 && this.count >= this.limit)
        return `${this.limit - 1}+`
      return this.count
    },
    hasOneDigitOnly() {
      return this.value.toString().length < 2
    },
  },
}
</script>
