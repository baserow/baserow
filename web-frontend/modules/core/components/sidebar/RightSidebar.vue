<template>
  <div class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <component
      :is="component"
      v-for="(component, index) in sidebarWorkspaceComponents"
      :key="'sidebarWorkspaceComponents' + index"
      :workspace="selectedWorkspace"
    ></component>
  </div>
</template>

<script>
export default {
  name: 'RightSidebar',
  props: {
    workspaces: {
      type: Array,
      required: true,
    },
    selectedWorkspace: {
      type: Object,
      required: true,
    },
    collapsed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    width: {
      type: Number,
      required: false,
      default: 42,
    },
  },
  data() {
    return {}
  },
  computed: {
    sidebarWorkspaceComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .flatMap((plugin) =>
          plugin.getRightSidebarWorkspaceComponents(this.selectedWorkspace)
        )
        .filter((component) => component !== null)
    },
  },
}
</script>
