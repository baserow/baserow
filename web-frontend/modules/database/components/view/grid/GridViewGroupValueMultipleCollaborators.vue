<template>
  <div class="grid-view__group-value-many-to-many">
    <div
      v-for="item in value"
      :key="item.id"
      class="field-multiple-collaborators__item"
    >
      <!-- An optimistically-created group only knows the id; resolve the name from the
           store so a new group shows its badge before the server display arrives. -->
      <template v-if="item.id != null">
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
