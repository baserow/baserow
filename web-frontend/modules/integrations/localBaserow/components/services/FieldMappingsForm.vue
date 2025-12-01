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
    value: {
      type: Array,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
  },
  computed: {
    fieldMappingMap() {
      return Object.fromEntries(
        this.value.map((fieldMapping) => [fieldMapping.field_id, fieldMapping])
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
      const existingMapping = this.value.some(
        ({ field_id: existingId }) => existingId === fieldId
      )
      const existingFieldIds = this.fields.map(({ id }) => id)

      // If the field has been removed in the meantime we want to ignore it
      const filteredValue = this.value.filter(({ field_id: fieldId }) =>
        existingFieldIds.includes(fieldId)
      )

      if (existingMapping) {
        if (changes === undefined) {
          this.$emit(
            'input',
            filteredValue.filter(
              ({ field_id: fieldIdToCheck }) => fieldIdToCheck !== fieldId
            )
          )
        } else {
          this.$emit(
            'input',
            filteredValue.map((fieldMapping) => {
              if (fieldMapping.field_id === fieldId) {
                return { ...fieldMapping, ...changes }
              }
              return fieldMapping
            })
          )
        }
      } else if (changes !== undefined) {
        this.$emit('input', [
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
