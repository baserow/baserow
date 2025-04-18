<template>
  <div style="height: 100%; display: flex; flex-direction: column">
    <Tabs
      offset
      full-height
      :route="$route"
      large-offset
      @click-disabled="clickDisabled(pages[$event])"
    >
      <Tab
        v-for="page in pages"
        :key="page.type"
        :title="page.name"
        :disabled="!page.navigable"
        :to="page.to"
        :icon="!page.navigable ? 'iconoir-lock' : null"
      >
        <NuxtChild :workspace="workspace" />
      </Tab>
    </Tabs>
    <component
      :is="page.deactivatedModal[0]"
      v-for="page in deactivatedPagesWithModal"
      :key="page.type"
      :ref="'deactivatedModal' + page.type"
      v-bind="page.deactivatedModal[1]"
      :workspace="workspace"
    ></component>
  </div>
</template>

<script>
export default {
  name: 'Settings',
  layout: 'app',
  async asyncData({ store, params, error }) {
    try {
      const workspace = await store.dispatch(
        'workspace/selectById',
        parseInt(params.workspaceId, 10)
      )
      return { workspace }
    } catch (e) {
      return error({ statusCode: 404, message: 'Workspace not found.' })
    }
  },
  computed: {
    workspaceSettingsPageTypes() {
      return Object.values(this.$registry.getAll('workspaceSettingsPage'))
    },
    pages() {
      // Build an array of settings page types they're permitted to view.
      const permittedPages = this.workspaceSettingsPageTypes.filter(
        (instance) => instance.hasPermission(this.workspace)
      )
      return permittedPages.map((instance) => {
        return {
          type: instance.type,
          name: instance.getName(),
          to: instance.getRoute(this.workspace),
          navigable: instance.isFeatureActive(this.workspace),
          deactivatedModal: instance.getFeatureDeactivatedModal(this.workspace),
        }
      })
    },
    deactivatedPagesWithModal() {
      return this.pages.filter((page) => {
        return !page.navigable && page.deactivatedModal
      })
    },
  },
  mounted() {
    this.$bus.$on('workspace-deleted', this.workspaceDeleted)
  },
  beforeDestroy() {
    this.$bus.$off('workspace-deleted', this.workspaceDeleted)
  },
  methods: {
    workspaceDeleted() {
      this.$nuxt.$router.push({ name: 'dashboard' })
    },
    clickDisabled(page) {
      const deactivatedModal = this.$refs['deactivatedModal' + page.type]
      if (deactivatedModal) {
        deactivatedModal[0].show()
      }
    },
  },
}
</script>
