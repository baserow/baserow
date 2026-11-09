<template>
  <div class="card-multiple-collaborators__list-wrapper">
    <div class="card-multiple-collaborators__list">
      <div
        v-for="item in value"
        :key="item.id"
        class="card-multiple-collaborators__item"
      >
        <template v-if="item.id && item.name">
          <span
            class="field-multiple-collaborators__name background-color--light-gray"
            >{{ getCollaboratorName(item, $store) }}</span
          >
          <CollaboratorAvatar
            v-if="value"
            class="field-multiple-collaborators__avatar"
            :subject="item"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'RowCardFieldMultipleCollaborators',
  height: 30,
  mixins: [collaboratorName],
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
