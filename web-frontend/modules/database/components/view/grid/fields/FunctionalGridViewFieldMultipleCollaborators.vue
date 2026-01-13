<template>
  <div ref="cell" class="grid-view__cell grid-field-many-to-many__cell">
    <div class="grid-field-many-to-many__list">
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
  </div>
</template>

<script>
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'FunctionalGridViewFieldMultipleCollaborators',
  mixins: [collaboratorName],
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
