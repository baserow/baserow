import { getCollaboratorName } from '@baserow/modules/core/utils/collaborator'
import CollaboratorAvatar from '@baserow/modules/database/components/field/CollaboratorAvatar'

export default {
  components: { CollaboratorAvatar },
  methods: {
    getCollaboratorName(collaboratorValue, store) {
      return getCollaboratorName(
        collaboratorValue,
        store ?? this.$store,
        this.$registry
      )
    },
    getCollaboratorNameInitials(collaboratorValue, store) {
      return this.getCollaboratorName(collaboratorValue, store)
        .slice(0, 1)
        .toUpperCase()
    },
  },
}
