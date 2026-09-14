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
        :name="groupByOption.name"
        :value="groupByOption.value"
      >
        {{ groupByOption.name }}
      </DropdownItem>
    </Dropdown>
    <FormGroup
      v-if="isMultipleSelect"
      :label="$t('aggregationGroupByForm.modeLabel')"
      class="margin-top-2"
    >
      <Dropdown
        :value="aggregationMode"
        fixed-items
        @change="modeChangedByUser($event)"
      >
        <DropdownItem
          value="complete"
          :name="$t('aggregationGroupByForm.completeSelection')"
        />
        <DropdownItem
          value="individual"
          :name="$t('aggregationGroupByForm.eachOption')"
        />
      </Dropdown>
    </FormGroup>
  </FormSection>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'AggregationGroupByForm',
  emits: ['value-changed', 'mode-changed'],
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
      aggregationMode: 'complete',
    }
  },
  computed: {
    isMultipleSelect() {
      return (
        this.tableFields.find((field) => field.id === this.aggregationGroupBy)
          ?.type === 'multiple_select'
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
        },
        { name: this.$t('aggregationGroupByForm.groupByNone'), value: 'none' },
      ])
    },
  },
  watch: {
    aggregationGroupBys: {
      handler(aggregationGroupBys) {
        this.aggregationMode = aggregationGroupBys[0]?.mode ?? 'complete'
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
          const validGroupByValues = this.groupByOptions.map(
            (item) => item.value
          )
          return validGroupByValues.includes(value)
        },
      },
    }
  },
  methods: {
    modeChangedByUser(value) {
      this.aggregationMode = value
      this.$emit('mode-changed', value)
    },
    groupByChangedByUser(value) {
      this.aggregationGroupBy = value
      this.$emit('value-changed', value)
    },
  },
}
</script>
