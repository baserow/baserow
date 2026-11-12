import { getSelectableCollaborators } from '@baserow/modules/core/utils/collaborator'

export default {
  computed: {
    workspaceCollaborators() {
      const workspace = this.$store.getters['workspace/get'](this.workspaceId)
      if (workspace) {
        // Fields without the option, like created by, can always hold identities.
        return getSelectableCollaborators(
          this.$store.getters['workspace/getCollaborators'](workspace.id),
          this.field.include_identities ?? true
        )
          .filter((collaborator) => !collaborator.to_be_deleted)
          .map((collaborator) => ({
            id: collaborator.user_id,
            name: collaborator.name,
            user_type: collaborator.user_type || 'human',
          }))
      }
      return this.field.available_collaborators
    },
    availableCollaborators() {
      // When converting from a CollaboratorField to another field it can happen
      // that this property is being computed with the value (this.value) of the
      // converted to field type. It can either be null, or not an array. In both cases
      // we can safely return an empty array.
      if (!Array.isArray(this.value)) {
        return []
      }

      const ids = new Set(this.value.map((item) => item.id))
      const result = this.workspaceCollaborators.filter(
        (item) => !ids.has(item.id)
      )
      return result
    },
  },
}
