<template>
  <div ref="cell" class="grid-view__cell active">
    <div v-if="value" class="field-last-modified-by">
      <div class="field-last-modified-by__name background-color--light-gray">
        <span class="field-last-modified-by__name-text">{{
          getCollaboratorName(value)
        }}</span>
      </div>
      <CollaboratorAvatar
        class="field-last-modified-by__avatar"
        :subject="value"
      />
    </div>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  mixins: [gridField, collaboratorName],
}
</script>
