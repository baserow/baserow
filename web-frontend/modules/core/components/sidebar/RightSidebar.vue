<template>
  <div class="sidebar">
    <component
      :is="component"
      v-for="(component, index) in sidebarWorkspaceComponents"
      :key="'sidebarWorkspaceComponents' + index"
      :workspace="workspace"
    ></component>
  </div>
</template>

<script>
export default {
  name: 'RightSidebar',
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    width: {
      type: Number,
      required: false,
      default: 400,
    },
  },
  computed: {
    sidebarWorkspaceComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .flatMap((plugin) =>
          plugin.getRightSidebarWorkspaceComponents(this.workspace)
        )
        .filter((component) => component !== null)
    },
  },
}
</script>
