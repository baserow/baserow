export default {
  computed: {
    workspaceCollaborators() {
      const workspace = this.$store.getters['workspace/getSelected']
      const workspaceUsers = workspace.users.filter(
        (user) => user.to_be_deleted === false
      )
      if (
        Object.prototype.hasOwnProperty.call(
          this.field,
          'available_collaborators'
        )
      ) {
        return this.field.available_collaborators
      } else {
        return workspaceUsers
      }
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
