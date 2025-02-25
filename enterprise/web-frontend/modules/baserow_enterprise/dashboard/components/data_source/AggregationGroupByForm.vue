<template>
  <FormSection
    :title="$t('aggregationGroupByForm.groupByFieldLabel')"
    class="margin-bottom-2"
  >
    <Dropdown
      :value="aggregationGroupBy"
      :show-search="true"
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
  data() {
    return {
      aggregationGroupBy: 'none',
    }
  },
  computed: {
    groupByOptions() {
      const tableFieldOptions = this.tableFields.map((field) => {
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
  methods: {
    groupByChangedByUser(value) {
      this.aggregationGroupBy = value
      this.$emit('value-changed', value)
    },
  },
}
</script>
