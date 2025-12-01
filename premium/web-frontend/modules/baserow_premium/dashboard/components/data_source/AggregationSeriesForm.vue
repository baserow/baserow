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
          :error="!disabled && fieldHasErrors('aggregation_type')"
          :disabled="disabled || loading"
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
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="values.field_id"
          :error="!disabled && fieldHasErrors('field_id')"
          :disabled="disabled || loading"
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
      <FormGroup
        small-label
        :label="$t('aggregationSeriesForm.chartType')"
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          :value="
            currentSeriesConfig.series_chart_type ||
            widget.default_series_chart_type
          "
          :error="fieldHasErrors('chart_type')"
          :disabled="disabled || loading"
          @change="seriesChartTypeChanged"
        >
          <DropdownItem
            v-for="variation in widgetVariations"
            :key="variation.params.default_series_chart_type"
            :name="variation.name"
            :value="variation.params.default_series_chart_type"
            :icon="variation.dropdownIcon"
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormSection>
    <FormSection v-if="aggregationSeries.length > 1">
      <ButtonText
        icon="iconoir-bin"
        type="secondary"
        :disabled="disabled || loading"
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
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    widget: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['id', 'field_id', 'aggregation_type'],
      values: {
        id: null,
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
    currentSeriesConfig() {
      const series = this.aggregationSeries[this.seriesIndex]
      return (
        this.widget.series_config.find(
          (item) => item.series_id === series.id
        ) || {}
      )
    },
    widgetVariations() {
      const widgetType = this.$registry.get('dashboardWidget', this.widget.type)
      return widgetType.variations
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
    seriesChartTypeChanged(chartType) {
      const seriesConfig = {
        series_id: this.aggregationSeries[this.seriesIndex].id,
        series_chart_type: chartType,
      }
      this.$emit('series-config-changed', seriesConfig)
    },
  },
}
</script>
