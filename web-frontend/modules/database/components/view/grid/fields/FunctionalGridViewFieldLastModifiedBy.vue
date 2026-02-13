<template>
  <div ref="cell" class="grid-view__cell">
    <div v-if="value" class="field-last-modified-by">
      <div class="field-last-modified-by__name background-color--light-gray">
        <span class="field-last-modified-by__name-text">{{
          getCollaboratorName(value, $store)
        }}</span>
      </div>
      <div class="field-last-modified-by__initials">
        {{ getCollaboratorNameInitials(value, $store) }}
      </div>
    </div>
  </div>
</template>

<script>
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'FunctionalGridViewFieldLastModifiedBy',
  mixins: [collaboratorName],
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
