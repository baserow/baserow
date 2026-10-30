<template>
  <div class="control__elements">
    <div
      v-if="value"
      class="field-last-modified-by field-last-modified-by--row-edit-field"
    >
      <div class="field-last-modified-by__name background-color--light-gray">
        <span class="field-last-modified-by__name-text">{{
          getCollaboratorName(value)
        }}</span>
      </div>
      <CollaboratorAvatar
            :field="field"
        class="field-last-modified-by__initials"
        :collaborator="value"
      />
    </div>
  </div>
</template>

<script>
import CollaboratorAvatar from '@baserow/modules/core/components/CollaboratorAvatar'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  components: { CollaboratorAvatar },
  mixins: [rowEditField, collaboratorName],
}
</script>
