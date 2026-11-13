import { getCollaboratorName } from '@baserow/modules/core/utils/collaborator'

export default {
  props: {
    field: { type: Object, default: null },
  },
  methods: {
    getCollaboratorName(collaboratorValue, store) {
      return getCollaboratorName(collaboratorValue, store ?? this.$store)
    },
  },
}
