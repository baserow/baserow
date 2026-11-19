<template>
  <component
    :is="plugin.getApplicationCreateFormComponent()"
    v-for="plugin in plugins"
    :key="plugin.getType()"
    :workspace="workspace"
  />
</template>

<script>
export default {
  props: { workspace: { type: Object, required: true } },
  computed: {
    plugins() {
      return Object.values(this.$registry.getAll('plugin')).filter((plugin) =>
        plugin.getApplicationCreateFormComponent()
      )
    },
  },
}
</script>
