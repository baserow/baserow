<template>
  <div>
    <FieldMappingForm
      v-for="field in filteredFields"
      :key="field.id"
      :field="field"
      :mapping="fieldMappingMap[field.id]"
      @update="updateFieldMapping(field.id, $event)"
    />
  </div>
</template>

<script>
import FieldMappingForm from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingForm'

export default {
  name: 'FieldMappingsForm',
  components: { FieldMappingForm },
  inject: ['workspace'],
  props: {
    modelValue: {
      type: Array,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
  },
  emits: ['update:modelValue'],
  computed: {
    fieldMappingMap() {
      return Object.fromEntries(
        this.modelValue.map((fieldMapping) => [
          fieldMapping.field_id,
          fieldMapping,
        ])
      )
    },
    filteredFields() {
      return this.fields.filter((field) => this.canWriteFieldValues(field))
    },
  },
  methods: {
    canWriteFieldValues(field) {
      return this.$hasPermission(
        'database.table.field.write_values',
        field,
        this.workspace.id
      )
    },
    updateFieldMapping(fieldId, changes) {
      const existingMapping = this.modelValue.some(
        ({ field_id: existingId }) => existingId === fieldId
      )
      const existingFieldIds = this.fields.map(({ id }) => id)

      // A mapping on a field that is gone is dropped. One on a trashed field
      // is sent back as it is, since the field list leaves it out and the
      // server replaces the mappings with what it gets.
      const filteredValue = this.modelValue.filter(
        ({ field_id: fieldId, trashed }) =>
          trashed === true || existingFieldIds.includes(fieldId)
      )

      if (existingMapping) {
        if (changes === undefined) {
          this.$emit(
            'update:modelValue',
            filteredValue.filter(
              ({ field_id: fieldIdToCheck }) => fieldIdToCheck !== fieldId
            )
          )
        } else {
          this.$emit(
            'update:modelValue',
            filteredValue.map((fieldMapping) => {
              if (fieldMapping.field_id === fieldId) {
                return { ...fieldMapping, ...changes }
              }
              return fieldMapping
            })
          )
        }
      } else if (changes !== undefined) {
        this.$emit('update:modelValue', [
          ...filteredValue,
          {
            enabled: true,
            field_id: fieldId,
            ...changes,
          },
        ])
      }
    },
  },
}
</script>
