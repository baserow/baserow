<template>
  <div class="control__elements">
    <div
      v-if="field.available_collaborators.length === 0"
      class="control--messages"
    >
      <p>{{ $t('formViewField.noCollaboratorsAvailable') }}</p>
    </div>
    <div v-for="option in field.available_collaborators" :key="option.id">
      <Checkbox
        :checked="value.findIndex((o) => o.id === option.id) !== -1"
        class="margin-bottom-1"
        @input=";[touch(), toggleValue(option.id, value)]"
        >{{ option.name }}</Checkbox
      >
    </div>
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
