import { getCollaboratorName } from '@baserow/modules/core/utils/collaborator'

export default {
  methods: {
    getCollaboratorName(collaboratorValue, store) {
      return getCollaboratorName(collaboratorValue, store ?? this.$store)
    },
    getCollaboratorNameInitials(collaboratorValue, store) {
      return this.getCollaboratorName(collaboratorValue, store)
        .slice(0, 1)
        .toUpperCase()
    },
  },
}
