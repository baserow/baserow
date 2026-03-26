<template>
  <div v-if="captchaEnabled" class="mb-24">
    <component
      :is="providerComponent"
      ref="providerWidget"
      :captcha-settings="captchaSettings"
      @token="onToken"
    />
  </div>
</template>

<script>
export default {
  name: 'CaptchaWidget',
  props: {
    context: {
      type: String,
      required: true,
    },
  },
  emits: ['token'],
  computed: {
    captchaSettings() {
      return this.$store.getters['settings/get']?.captcha || {}
    },
    captchaEnabled() {
      return (
        this.captchaSettings.enabled &&
        Array.isArray(this.captchaSettings.enabled_contexts) &&
        this.captchaSettings.enabled_contexts.includes(this.context) &&
        this.providerComponent !== null
      )
    },
    providerComponent() {
      const providerType = this.captchaSettings.provider
      if (!providerType) {
        return null
      }
      if (!this.$registry.exists('captchaProvider', providerType)) {
        return null
      }
      return this.$registry.get('captchaProvider', providerType).getComponent()
    },
  },
  methods: {
    onToken(token) {
      this.$emit('token', token)
    },
    reset() {
      if (this.$refs.providerWidget) {
        this.$refs.providerWidget.reset()
      }
      this.$emit('token', '')
    },
  },
}
</script>
