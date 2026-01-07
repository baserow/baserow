import { notifyIf } from '@baserow/modules/core/utils/error'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'

/**
 * Some helper method to modify workspaces used by the sidebar and dashboard.
 */
export default {
  emits: ['selected'],

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
    async selectWorkspace(workspace) {
      await this.$store.dispatch('workspace/select', workspace)
      await this.$router.push({
        name: 'workspace',
        params: { workspaceId: workspace.id },
      })
      await pageFinished()
      await nextTick()
      this.$emit('selected')
    },
  },
}
