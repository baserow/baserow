<template>
  <div class="control__elements">
    <div v-if="workspaceCollaborators.length === 0" class="control--messages">
      <p>{{ $t('formViewField.noCollaboratorsAvailable') }}</p>
    </div>
    <template v-for="group in groups" :key="group.name">
      <div v-if="group.label" class="form-view__field-group">
        {{ group.label }}
      </div>
      <div v-for="option in group.options" :key="option.id">
        <Checkbox
          :checked="value.findIndex((o) => o.id === option.id) !== -1"
          class="margin-bottom-1"
          @input=";[touch(), toggleValue(option.id, value)]"
          >{{ option.name }}</Checkbox
        >
      </div>
    </template>
    <div v-if="!required" class="margin-top-1">
      <a @click=";[touch(), clear(value)]">clear value</a>
    </div>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import collaboratorField from '@baserow/modules/database/mixins/collaboratorField'

export default {
  name: 'FormViewFieldMultipleCollaboratorsCheckboxes',
  mixins: [rowEditField, collaboratorField],
  emits: ['update'],
  computed: {
    groups() {
      const isIdentity = (collaborator) => collaborator.user_type === 'identity'
      return [
        {
          name: 'people',
          options: this.workspaceCollaborators.filter(
            (collaborator) => !isIdentity(collaborator)
          ),
        },
        {
          name: 'identities',
          label: this.$t('fieldmultipleCollaboratorsDropdown.identities'),
          options: this.workspaceCollaborators.filter(isIdentity),
        },
      ].filter((group) => group.options.length > 0)
    },
  },
  methods: {
    toggleValue(id, oldValue) {
      const index = oldValue.findIndex((option) => option.id === id)

      if (index === -1) {
        this.updateValue(id, oldValue)
      } else {
        this.removeValue(null, oldValue, id)
      }
    },
    clear(oldValue) {
      const newValue = []

      if (JSON.stringify(newValue) !== JSON.stringify(oldValue)) {
        this.$emit('update', newValue, oldValue)
      }
    },
  },
}
</script>
