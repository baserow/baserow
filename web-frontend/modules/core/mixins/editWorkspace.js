import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Some helper methods to modify workspaces used by the dashboard.
 */
export default {
  methods: {
    setLoading(workspace, value) {
      this.$store.dispatch('workspace/setItemLoading', { workspace, value })
    },
    enableRename() {
      this.$refs.context.hide()
      this.$refs.rename.edit()
    },
    async renameWorkspace(workspace, event) {
      this.setLoading(workspace, true)

      try {
        await this.$store.dispatch('workspace/update', {
          workspace,
          values: {
            name: event.value,
          },
        })
      } catch (error) {
        this.$refs.rename.set(event.oldValue)
        notifyIf(error, 'workspace')
      }

      this.setLoading(workspace, false)
    },
  },
}
