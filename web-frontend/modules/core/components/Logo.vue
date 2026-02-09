<template>
  <!-- TODO MIG component :is="getComponent()" v-if="getComponent()" /-->
  <!-- must be in sync with modules/baserow_enterprise/components/EnterpriseLogo.vue -->
  <div class="logo">
    <img
      src="@baserow/modules/core/static/img/logo.svg?url"
      v-bind="$attrs"
      :class="[$attrs.class]"
    />
  </div>
</template>

<script>
export default {
  name: 'Logo',
  methods: {
    getComponent() {
      return (
        Object.values(this.$registry.getAll('plugin'))
          .filter((plugin) => plugin.getLogoComponent() !== null)
          .sort(
            (p1, p2) => p2.getLogoComponentOrder() - p1.getLogoComponentOrder()
          )
          .map((plugin) => plugin.getLogoComponent())[0] || null
      )
    },
  },
}
</script>
