<template>
  <div class="grid-view__group-value-many-to-many">
    <div
      v-for="item in value"
      :key="item.id"
      class="field-multiple-collaborators__item"
    >
      <template v-if="item.id && item.name">
        <div
          class="field-multiple-collaborators__name background-color--light-gray"
        >
          <span class="field-multiple-collaborators__name-text">{{
            getCollaboratorName(item, $store)
          }}</span>
        </div>
        <div class="field-multiple-collaborators__initials">
          {{ getCollaboratorNameInitials(item, $store) }}
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'GridViewGroupValueMultipleCollaborators',
  mixins: [collaboratorName],
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
