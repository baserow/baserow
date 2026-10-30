<template>
  <div ref="cell" class="grid-view__cell">
    <div v-if="value" class="field-last-modified-by">
      <div class="field-last-modified-by__name background-color--light-gray">
        <span class="field-last-modified-by__name-text">{{
          getCollaboratorName(value, $store)
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
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'FunctionalGridViewFieldLastModifiedBy',
  components: { CollaboratorAvatar },
  mixins: [collaboratorName],
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
