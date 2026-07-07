<template>
  <div ref="cell" class="grid-view__cell grid-field-many-to-many__cell active">
    <div ref="dropdownLink" class="grid-field-many-to-many__list">
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
              getCollaboratorName(item)
            }}</span>
            <a
              v-if="!readOnly"
              class="grid-field-many-to-many__remove"
              @click.prevent="removeValue($event, value, item.id)"
            >
              <i class="iconoir-cancel"></i>
            </a>
          </div>
          <div class="field-multiple-collaborators__initials">
            {{ getCollaboratorNameInitials(item) }}
          </div>
        </template>
      </div>
      <a
        v-if="!readOnly"
        class="grid-field-many-to-many__item grid-field-many-to-many__item--link"
        @click.prevent="toggleDropdown()"
      >
        <i class="iconoir-plus"></i>
      </a>
    </div>
    <FieldCollaboratorDropdown
      v-if="!readOnly"
      ref="dropdown"
      :collaborators="availableCollaborators"
      :show-input="false"
      :show-empty-value="false"
      class="dropdown--floating"
      @show="editing = true"
      @hide="editing = false"
      @input="updateValue($event, value)"
    ></FieldCollaboratorDropdown>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import collaboratorField from '@baserow/modules/database/mixins/collaboratorField'
import FieldCollaboratorDropdown from '@baserow/modules/database/components/field/FieldCollaboratorDropdown'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  components: { FieldCollaboratorDropdown },
  mixins: [gridField, collaboratorField, collaboratorName],
  emits: ['editing-changed'],
  data() {
    return {
      editing: false,
    }
  },
  watch: {
    editing(editing) {
      this.$emit('editing-changed', editing)
    },
  },
}
</script>
