<template>
  <div class="aggregation-series-form">
    <FormSection>
      <FormGroup
        small-label
        :label="$t('aggregationSeriesForm.aggregationTypeLabel')"
        required
        horizontal
        horizontal-narrow
        class="margin-bottom-2"
      >
        <Dropdown
          :value="values.aggregation_type"
          :error="fieldHasErrors('aggregation_type')"
          @change="aggregationTypeChanged"
        >
          <DropdownItem
            v-for="aggregation in aggregationTypesAvailableForSelection"
            :key="aggregation.getType()"
            :name="aggregation.getName()"
            :value="aggregation.getType()"
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('aggregationSeriesForm.aggregationFieldLabel')"
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          v-model="values.field_id"
          :error="fieldHasErrors('field_id')"
          @change="v$.values.field_id.$touch"
        >
          <DropdownItem
            v-for="field in fieldsAvailableForSelection"
            :key="field.id"
            :name="field.name"
            :value="field.id"
            :icon="fieldIconClass(field)"
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormSection>
    <FormSection v-if="aggregationSeries.length > 1">
      <ButtonText
        icon="iconoir-bin"
        type="secondary"
        @click="$emit('delete-series', seriesIndex)"
        >{{ $t('aggregationSeriesForm.deleteSeries') }}</ButtonText
      >
    </FormSection>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { required } from '@vuelidate/validators'

const includes = (array) => (value) => {
  return array.includes(value)
}

export default {
  name: 'AggregationSeriesForm',
  mixins: [form],
  props: {
    tableFields: {
      type: Array,
      required: true,
    },
    aggregationSeries: {
      type: Array,
      required: true,
    },
    seriesIndex: {
      type: Number,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['field_id', 'aggregation_type'],
      values: {
        field_id: null,
        aggregation_type: null,
      },
      skipFirstValuesEmit: true,
    }
  },
  computed: {
    groupedAggregationTypes() {
      const allAggregationTypes =
        this.$registry.getOrderedList('groupedAggregation')
      return allAggregationTypes.filter((aggType) => {
        return this.tableFields.some((tableField) =>
          aggType.fieldIsCompatible(tableField)
        )
      })
    },
    aggregationTypesAvailableForSelection() {
      return this.groupedAggregationTypes.filter(
        (aggregationType) =>
          this.isSeriesRepeated(
            this.values.field_id,
            aggregationType.getType()
          ) === false ||
          this.values.aggregation_type === aggregationType.getType()
      )
    },
    aggregationTypeNames() {
      return this.groupedAggregationTypes.map((aggType) => aggType.getType())
    },
    usedSeries() {
      return this.aggregationSeries
        .filter(
          (series) =>
            series.aggregation_type !== null && series.field_id !== null
        )
        .map((series) => {
          return `${series.field_id}_${series.aggregation_type}`
        })
    },
    compatibleFields() {
      if (!this.values.aggregation_type) {
        return []
      }
      const aggType = this.$registry.get(
        'groupedAggregation',
        this.values.aggregation_type
      )
      return this.tableFields.filter((tableField) =>
        aggType.fieldIsCompatible(tableField)
      )
    },
    fieldsAvailableForSelection() {
      return this.compatibleFields.filter(
        (field) =>
          this.isSeriesRepeated(field.id, this.values.aggregation_type) ===
            false || this.values.field_id === field.id
      )
    },
    compatibleTableFieldIds() {
      return this.compatibleFields.map((field) => field.id)
    },
  },
  mounted() {
    this.v$.$touch()
  },
  validations() {
    const self = this
    return {
      values: {
        aggregation_type: {
          required,
          isValidAggregationType: (value) => {
            const aggregationTypeNames = self.aggregationTypeNames
            return includes(aggregationTypeNames)(value)
          },
        },
        field_id: {
          required,
          isValidFieldId: (value) => {
            const compatibleTableFieldIds = self.compatibleTableFieldIds
            return includes(compatibleTableFieldIds)(value)
          },
        },
      },
    }
  },
  methods: {
    isSeriesRepeated(fieldId, aggregationType) {
      if (fieldId === null || aggregationType === null) {
        return false
      }
      return this.usedSeries.includes(`${fieldId}_${aggregationType}`)
    },
    fieldIconClass(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.iconClass
    },
    aggregationTypeChanged(aggregationType) {
      this.values.aggregation_type = aggregationType
      const aggType = this.$registry.get('groupedAggregation', aggregationType)
      const field = this.tableFields.find(
        (field) => field.id === this.values.field_id
      )
      if (
        (field && !aggType.fieldIsCompatible(field)) ||
        this.fieldHasErrors('field_id')
      ) {
        this.values.field_id = null
      }
      this.v$.values.aggregation_type.$touch()
    },
  },
}
</script>
