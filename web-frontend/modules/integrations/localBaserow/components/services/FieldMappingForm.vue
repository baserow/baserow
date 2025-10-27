<template>
  <div>
    <FormGroup
      v-for="field in filteredFields"
      :key="field.id"
      small-label
      :label="field.name"
      required
      class="margin-bottom-2"
    >
      <FieldMapping
        :field-mapping="field.mapping"
        :placeholder="$t('upsertRowWorkflowActionForm.fieldMappingPlaceholder')"
        @change="updateFieldMapping(field.id, $event)"
      />
      <template #after-input>
        <div :ref="`editFieldMappingOpener-${field.id}`">
          <ButtonIcon
            type="secondary"
            icon="iconoir-more-vert"
            @click="openContext(field)"
          />
        </div>
        <FieldMappingContext
          :ref="`fieldMappingContext-${field.id}`"
          :field-mapping="field.mapping"
          @edit="updateFieldMapping(field.id, $event)"
        />
      </template>
    </FormGroup>
  </div>
</template>

<script>
import FieldMapping from '@baserow/modules/integrations/localBaserow/components/services/FieldMapping'
import FieldMappingContext from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingContext'

export default {
  name: 'FieldMappingForm',
  components: { FieldMappingContext, FieldMapping },
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
    filteredFields() {
      return this.fields
        .map((field) => ({
          ...field,
          mapping: this.getFieldMapping(field.id),
        }))
        .filter((field) => this.canWriteFieldValues(field))
    },
  },
  methods: {
    openContext(field) {
      this.$refs[`fieldMappingContext-${field.id}`][0].toggle(
        this.$refs[`editFieldMappingOpener-${field.id}`][0],
        'bottom',
        'left',
        4
      )
    },
    canWriteFieldValues(field) {
      return this.$hasPermission(
        'database.table.field.write_values',
        field,
        this.workspace.id
      )
    },
    getFieldMapping(fieldId) {
      return (
        this.value.find(
          (fieldMapping) => fieldMapping.field_id === fieldId
        ) || { enabled: true, field_id: fieldId, value: {} }
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
        const newMapping = filteredValue.map((fieldMapping) => {
          if (fieldMapping.field_id === fieldId) {
            return { ...fieldMapping, ...changes }
          }
          return fieldMapping
        })
        this.$emit('input', newMapping)
      } else {
        const newMapping = filteredValue
        newMapping.push({
          enabled: true,
          field_id: fieldId,
          ...changes,
        })
        this.$emit('input', newMapping)
      }
    },
  },
}
</script>
