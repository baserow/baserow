import { getFieldCollaborators } from '@baserow/modules/core/utils/collaborator'

export default {
  computed: {
    workspaceCollaborators() {
      return getFieldCollaborators(this.$store, this.field, this.workspaceId)
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
