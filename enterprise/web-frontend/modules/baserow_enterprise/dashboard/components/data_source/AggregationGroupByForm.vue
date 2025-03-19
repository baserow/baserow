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
  </FormSection>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'

const includesIfSet = (array) => (value) => {
  if (value === null || value === undefined) {
    return true
  }
  return array.includes(value)
}

export default {
  name: 'AggregationGroupByForm',
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
        { name: this.$t('aggregationGroupByForm.groupByRowId'), value: null },
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
    const self = this
    return {
      aggregationGroupBy: {
        isValidGroupBy: (value) => {
          const validGroupByValues = self.groupByOptions.map(
            (item) => item.value
          )
          return includesIfSet(validGroupByValues)(value)
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
