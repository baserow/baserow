<template>
  <span class="array-field__multiple-collaborators-container">
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
        <CollaboratorAvatar
            :field="field"
          class="field-multiple-collaborators__initials"
          :collaborator="item"
        />
      </template>
    </div>
  </span>
</template>

<script>
import CollaboratorAvatar from '@baserow/modules/core/components/CollaboratorAvatar'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'FunctionalFormulaMultipleCollaboratorsArrayItem',
  components: { CollaboratorAvatar },
  mixins: [collaboratorName],
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
