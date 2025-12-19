<template>
  <Toast type="info-neutral" icon="iconoir-warning-triangle">
    <template #title>{{ $t('userSessionExpiredToast.title') }}</template>
    <span> {{ $t('userSessionExpiredToast.content') }}</span>
  </Toast>
</template>

<script>
import Toast from '@baserow/modules/core/components/toasts/Toast'
export default {
  name: 'UserSessionExpiredToast',
  components: {
    Toast,
  },
  mounted() {
    setTimeout(() => {
      this.acknowledge()
    }, 7000)
  },
  beforeUnmount() {
    this.acknowledge()
  },
  methods: {
    acknowledge() {
      this.$store.dispatch('toast/setUserSessionExpired', false)
    },
  },
}
</script>
