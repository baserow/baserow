export default {
  methods: {
    getCollaboratorName(collaboratorValue, store) {
      if (store === undefined) {
        store = this.$store
      }

      // Workaround for field conversion not to produce console errors
      if (
        !collaboratorValue ||
        typeof collaboratorValue !== 'object' ||
        (!collaboratorValue.id && !collaboratorValue.name)
      ) {
        return ''
      }

      // If workspaces are unavailable, public views are served
      const workspaces = store.getters['workspace/getAll']
      if (workspaces.length === 0) {
        return collaboratorValue.name
      }

      // Otherwise, get name from the store to reflect real-time updates
      const user = store.getters['workspace/getUserById'](collaboratorValue.id)
      if (user) {
        return user.name
      }

      // Fallback if for some reason the user is missing from the store
      return collaboratorValue.name
    },
    getCollaboratorNameInitials(collaboratorValue, store) {
      return this.getCollaboratorName(collaboratorValue, store)
        .slice(0, 1)
        .toUpperCase()
    },
  },
}
