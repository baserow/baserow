<template>
  <FormSection
    :title="$t('aggregationSortByForm.sortByFieldLabel')"
    class="margin-bottom-2"
  >
    <Dropdown
      :value="sortByField"
      :show-search="true"
      fixed-items
      class="margin-bottom-1"
      :error="v$.sortByField?.$error || false"
      @change="sortByFieldChangedByUser($event)"
    >
      <DropdownItem
        :name="$t('aggregationSortByForm.none')"
        :value="null"
      ></DropdownItem>
      <DropdownItem
        v-for="field in allowedSortFields"
        :key="field.id"
        :name="field.name"
        :value="field.id"
        :icon="fieldIconClass(field)"
      >
      </DropdownItem>
    </Dropdown>
    <SegmentControl
      :active-index="orderByIndex"
      :segments="orderByOptions"
      :initial-active-index="orderByIndex"
      @update:activeIndex="orderByChangedByUser"
    ></SegmentControl>
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
    allowedSortFields: {
      type: Array,
      required: true,
    },
    aggregationSorts: {
      type: Array,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      sortByField: null,
      orderByIndex: 0,
    }
  },
  computed: {
    orderByOptions() {
      return [
        { label: this.$t('aggregationSortByForm.ascending'), value: 'ASC' },
        { label: this.$t('aggregationSortByForm.descending'), value: 'DESC' },
      ]
    },
  },
  watch: {
    aggregationSorts: {
      handler(aggregationSorts) {
        if (aggregationSorts.length !== 0) {
          this.sortByField = aggregationSorts[0].field
          this.orderByIndex = this.orderByOptions.findIndex(
            (item) => item.value === aggregationSorts[0].order_by
          )
        }
      },
      immediate: true,
    },
  },
  mounted() {
    this.v$.$validate(true)
  },
  validations() {
    const self = this
    return {
      sortByField: {
        isValidSortFieldId: (value) => {
          const ids = self.allowedSortFields.map((item) => item.id)
          return includesIfSet(ids)(value)
        },
      },
    }
  },
  methods: {
    sortByFieldChangedByUser(value) {
      this.sortByField = value
      this.$emit('value-changed', {
        field: value,
        order_by: this.orderByOptions[this.orderByIndex].value,
      })
    },
    orderByChangedByUser(index) {
      this.orderByIndex = index
      this.$emit('value-changed', {
        field: this.sortByField,
        order_by: this.orderByOptions[index].value,
      })
    },
    fieldIconClass(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.iconClass
    },
  },
}
</script>
