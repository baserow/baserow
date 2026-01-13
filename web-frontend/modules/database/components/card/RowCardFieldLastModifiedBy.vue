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
    <div v-if="value" class="field-last-modified-by__initials">
      {{ getCollaboratorNameInitials(value, $store) }}
    </div>
  </div>
</template>

<script>
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'RowCardFieldLastModifiedBy',
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
