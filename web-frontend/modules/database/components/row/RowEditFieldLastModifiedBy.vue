<template>
  <div class="control__elements">
    <BadgeCollaborator
      v-if="value"
      :initials="getCollaboratorNameInitials(value)"
    >
      {{ getCollaboratorName(value) }}
    </BadgeCollaborator>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  mixins: [rowEditField, collaboratorName],
}
</script>
