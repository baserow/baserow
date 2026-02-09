<template>
  <!-- must be in sync with `modules/core/components/Logo.vue` apart from the label. -->
  <div class="logo">
    <div v-if="showLabel()" class="logo__label">by Baserow</div>
    <img :src="getLogoUrl()" v-bind="$attrs" />
  </div>
</template>

<script>
export default {
  name: 'EnterpriseLogo',
  methods: {
    showLabel() {
      const settings = this.$store.getters['settings/get']
      return !!settings.co_branding_logo
    },
    getLogoUrl(parent) {
      const baserowLogo = require('@baserow/modules/core/static/img/logo.svg?url')
      const settings = this.$store.getters['settings/get']
      if (settings.co_branding_logo) {
        return settings.co_branding_logo.url
      }
      return baserowLogo
    },
  },
}
</script>
