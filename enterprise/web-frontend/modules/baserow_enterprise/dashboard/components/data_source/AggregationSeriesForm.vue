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
          v-model="values.aggregation_type"
          :error="fieldHasErrors('aggregation_type')"
          @change="v$.values.aggregation_type.$touch"
        >
          <DropdownItem
            v-for="viewAggregation in viewAggregationTypes"
            :key="viewAggregation.getType()"
            :name="viewAggregation.getName()"
            :value="viewAggregation.getType()"
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
          :disabled="compatibleFields.length === 0"
          @change="v$.values.field_id.$touch"
        >
          <DropdownItem
            v-for="field in compatibleFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
            :icon="fieldIconClass(field)"
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormSection>
    <FormSection>
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
      emitValuesOnReset: false,
    }
  },
  computed: {
    viewAggregationTypes() {
      return this.$registry.getOrderedList('viewAggregation')
    },
    aggregationTypeNames() {
      return this.viewAggregationTypes.map((aggType) => aggType.getType())
    },
    compatibleFields() {
      if (!this.values.aggregation_type) {
        return []
      }
      const aggType = this.$registry.get(
        'viewAggregation',
        this.values.aggregation_type
      )
      return this.tableFields.filter((tableField) =>
        aggType.fieldIsCompatible(tableField)
      )
    },
    compatibleTableFieldIds() {
      return this.compatibleFields.map((field) => field.id)
    },
  },
  watch: {
    'values.aggregation_type': {
      handler(aggregationType) {
        if (
          aggregationType !== null &&
          aggregationType !== this.defaultValues.aggregation_type &&
          this.values.field_id !== null
        ) {
          // If both the field and aggregation type
          // are selected, check if they are still
          // compatible.
          const aggType = this.$registry.get('viewAggregation', aggregationType)
          const field = this.tableFields.filter(
            (field) => field.id === this.values.field_id
          )
          if (!aggType.fieldIsCompatible(field)) {
            this.values.field_id = null
          }
        }
      },
      immediate: true,
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
    fieldIconClass(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.iconClass
    },
  },
}
</script>
