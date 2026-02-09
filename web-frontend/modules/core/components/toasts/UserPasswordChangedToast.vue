<template>
  <Toast type="info-primary" icon="iconoir-warning-triangle">
    <template #title>{{ $t('userPasswordChangedToast.title') }}</template>
    <span>{{ $t('userPasswordChangedToast.content') }}</span>
  </Toast>
</template>

<script>
import Toast from './Toast.vue'
export default {
  name: 'UserPasswordChangedToast',
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
      this.$store.dispatch('toast/setUserPasswordChanged', false)
    },
  },
}
</script>
