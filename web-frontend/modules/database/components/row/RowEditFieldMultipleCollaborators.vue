<template>
  <div class="control__elements">
    <span v-if="!readOnly" ref="dropdownLink" class="row-modal__choose-button">
      <ButtonText
        type="secondary"
        icon="iconoir-plus"
        @click.prevent="$refs.dropdown.toggle($refs.dropdownLink)"
      >
        {{ $t('rowEditFieldMultipleCollaborators.addCollaborator') }}
      </ButtonText>

      <FieldCollaboratorDropdown
        v-if="!readOnly"
        ref="dropdown"
        :collaborators="availableCollaborators"
        :disabled="readOnly"
        :show-input="false"
        fixed-items
        :show-empty-value="false"
        :class="{ 'dropdown--error': touched && !valid }"
        @input="updateValue($event, value)"
        @hide="touch()"
      ></FieldCollaboratorDropdown>
    </span>

    <ul class="field-multiple-collaborators__items">
      <li
        v-for="item in value"
        :key="item.id"
        class="field-multiple-collaborators__item field-multiple-collaborators__item--row-edit"
      >
        <template v-if="item.id && item.name">
          <BadgeCollaborator
            :remove-icon="!readOnly"
            :initials="getCollaboratorNameInitials(item)"
            @remove="removeValue($event, value, item.id)"
          >
            {{ getCollaboratorName(item) }}
          </BadgeCollaborator>
        </template>
      </li>
    </ul>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import collaboratorField from '@baserow/modules/database/mixins/collaboratorField'
import FieldCollaboratorDropdown from '@baserow/modules/database/components/field/FieldCollaboratorDropdown'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'RowEditFieldMultipleCollaborators',
  components: { FieldCollaboratorDropdown },
  mixins: [rowEditField, collaboratorField, collaboratorName],
}
</script>
