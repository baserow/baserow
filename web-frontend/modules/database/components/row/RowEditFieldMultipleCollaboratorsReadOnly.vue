<template>
  <div class="control__elements">
    <ul class="field-multiple-collaborators__items">
      <li
        v-for="item in value"
        :key="item.id"
        class="field-multiple-collaborators__item field-multiple-collaborators__item--row-edit"
      >
        <template v-if="item.id && item.name">
          <div
            class="field-multiple-collaborators__name background-color--light-gray"
          >
            <span class="field-multiple-collaborators__name-text">{{
              getCollaboratorName(item)
            }}</span>
          </div>
          <CollaboratorAvatar
            :field="field"
            class="field-multiple-collaborators__initials"
            :collaborator="item"
          />
        </template>
      </li>
    </ul>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import CollaboratorAvatar from '@baserow/modules/core/components/CollaboratorAvatar'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import collaboratorField from '@baserow/modules/database/mixins/collaboratorField'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'RowEditFieldMultipleCollaboratorsReadOnly',
  components: { CollaboratorAvatar },
  mixins: [rowEditField, collaboratorField, collaboratorName],
}
</script>
