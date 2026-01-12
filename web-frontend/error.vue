<template>
  <component :is="errorPageType.getComponent()" :error="error" />
</template>

<script>
export default {
  props: {
    error: {
      type: Object,
      required: true,
    },
  },
  computed: {
    errorPageType() {
      return this.$registry
        .getOrderedList('errorPage')
        .reverse()
        .find((errorPageType) => errorPageType.isApplicable(this.error))
    },
  },
}
</script>
