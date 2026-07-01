<template>
  <component :is="errorPageType.getComponent()" :error="error" />
</template>

<script>
import { computed } from 'vue'

export default {
  props: {
    error: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const { $i18n } = useNuxtApp()
    const message = computed(
      () => props.error?.message || $i18n.t('common.wrong')
    )

    useHead(() => ({
      title: message.value,
    }))
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
