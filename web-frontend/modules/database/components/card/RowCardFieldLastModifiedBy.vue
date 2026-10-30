<template>
  <div class="field-last-modified-by field-last-modified-by--card">
    <div
      v-if="value"
      class="field-last-modified-by__name background-color--light-gray"
    >
      <span class="field-last-modified-by__name-text">{{
        getCollaboratorName(value, $store)
      }}</span>
    </div>
    <CollaboratorAvatar
            v-if="value"
      :field="field"
      class="field-last-modified-by__initials"
      :collaborator="value"
    />
  </div>
</template>

<script>
import CollaboratorAvatar from '@baserow/modules/core/components/CollaboratorAvatar'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'RowCardFieldLastModifiedBy',
  components: { CollaboratorAvatar },
  height: 30,
  mixins: [collaboratorName],
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
