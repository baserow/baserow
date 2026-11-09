<template>
  <component
    :is="subjectType.avatarComponent"
    :subject="displaySubject"
    size="medium"
  />
</template>

<script>
import {
  getCollaboratorName,
  getCollaboratorSubjectType,
} from '@baserow/modules/core/utils/collaborator'

export default {
  props: {
    subject: { type: Object, required: true },
  },
  computed: {
    subjectType() {
      return getCollaboratorSubjectType(this.subject, this.$registry)
    },
    displaySubject() {
      return {
        ...this.subject,
        name: getCollaboratorName(this.subject, this.$store, this.$registry),
      }
    },
  },
}
</script>
