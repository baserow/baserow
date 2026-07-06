import { notifyIf } from '@baserow/modules/core/utils/error'
import { nameContainsNoUrl } from '@baserow/modules/core/validators'

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
      // The name is edited inline without a form, so there is no place to show
      // a validation error. Show a toast notification instead and revert the
      // name.
      if (!nameContainsNoUrl(event.value)) {
        this.$refs.rename.set(event.oldValue)
        this.$store.dispatch('toast/error', {
          title: this.$t('editWorkspace.invalidNameTitle'),
          message: this.$t('error.nameContainsUrl'),
        })
        return
      }

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
