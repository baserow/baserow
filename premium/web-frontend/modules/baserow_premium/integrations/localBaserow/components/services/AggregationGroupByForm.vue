<template>
  <FormSection
    :title="$t('aggregationGroupByForm.groupByFieldLabel')"
    class="margin-bottom-2"
  >
    <Dropdown
      :value="aggregationGroupBy"
      :show-search="true"
      :error="v$.aggregationGroupBy?.$error || false"
      fixed-items
      @change="groupByChangedByUser($event)"
    >
      <DropdownItem
        v-for="groupByOption in groupByOptions"
        :key="groupByOption.id"
        v-tooltip="
          groupByOption.disabled
            ? $t('aggregationGroupByForm.rowIdDisabledTooltip')
            : null
        "
        :name="groupByOption.name"
        :value="groupByOption.value"
        :disabled="groupByOption.disabled || false"
      >
        {{ groupByOption.name }}
      </DropdownItem>
    </Dropdown>
  </FormSection>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'AggregationGroupByForm',
  emits: ['value-changed'],
  props: {
    tableFields: {
      type: Array,
      required: true,
    },
    aggregationGroupBys: {
      type: Array,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      aggregationGroupBy: 'none',
    }
  },
  computed: {
    canGroupByRowId() {
      const primaryField = this.tableFields.find((field) => field.primary)
      return (
        primaryField &&
        this.$registry
          .get('field', primaryField.type)
          .getDocsDataType(primaryField) !== 'array'
      )
    },
    compatibleFields() {
      return this.tableFields.filter((field) =>
        this.$registry.exists('groupedAggregationGroupedBy', field.type)
      )
    },
    groupByOptions() {
      const tableFieldOptions = this.compatibleFields.map((field) => {
        return {
          name: field.name,
          value: field.id,
        }
      })
      return tableFieldOptions.concat([
        {
          name: this.$t('aggregationGroupByForm.groupByRowId'),
          value: null,
          disabled: !this.canGroupByRowId,
        },
        { name: this.$t('aggregationGroupByForm.groupByNone'), value: 'none' },
      ])
    },
  },
  watch: {
    aggregationGroupBys: {
      handler(aggregationGroupBys) {
        if (aggregationGroupBys.length === 0) {
          this.aggregationGroupBy = 'none'
        } else {
          this.aggregationGroupBy = aggregationGroupBys[0].field_id
        }
      },
      immediate: true,
    },
  },
  mounted() {
    this.v$.$touch()
  },
  validations() {
    return {
      aggregationGroupBy: {
        isValidGroupBy: (value) => {
          const validGroupByValues = this.groupByOptions
            .filter((item) => !item.disabled)
            .map((item) => item.value)
          return validGroupByValues.includes(value)
        },
      },
    }
  },
  methods: {
    groupByChangedByUser(value) {
      this.aggregationGroupBy = value
      this.$emit('value-changed', value)
    },
  },
}
</script>
