<template>
  <FormSection
    :title="$t('aggregationSortByForm.sortByFieldLabel')"
    class="margin-bottom-2"
  >
    <Dropdown
      :value="sortReference"
      :show-search="true"
      fixed-items
      class="margin-bottom-1"
      :error="v$.sortReference?.$error || false"
      @change="sortReferenceChangedByUser($event)"
    >
      <DropdownItem
        :name="$t('aggregationSortByForm.none')"
        :value="null"
      ></DropdownItem>
      <DropdownItem
        v-for="allowedSortReference in allowedSortReferences"
        :key="allowedSortReference.reference"
        :name="allowedSortReference.name"
        :value="allowedSortReference.reference"
        :icon="fieldIconClass(allowedSortReference.field)"
      >
      </DropdownItem>
    </Dropdown>
    <SegmentControl
      v-if="aggregationSorts.length > 0 && v$.sortReference?.$error === false"
      ref="sortDirectionSegment"
      :active-index="orderDirectionIndex"
      :segments="orderDirectionOptions"
      :initial-active-index="orderDirectionIndex"
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
  name: 'AggregationSortByForm',
  props: {
    allowedSortReferences: {
      type: Array,
      required: true,
    },
    aggregationSorts: {
      type: Array,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      sortReference: null,
      orderDirectionIndex: 0,
    }
  },
  computed: {
    orderDirectionOptions() {
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
          this.sortReference = aggregationSorts[0].reference
          this.orderDirectionIndex = this.orderDirectionOptions.findIndex(
            (item) => item.value === aggregationSorts[0].direction
          )
          if (this.$refs.sortDirectionSegment) {
            this.$refs.sortDirectionSegment.reset()
          }
        } else {
          this.sortReference = null
          this.orderDirectionIndex = 0
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
      sortReference: {
        isValidSortReference: (value) => {
          const sortReferences = self.allowedSortReferences.map(
            (item) => item.reference
          )
          return includesIfSet(sortReferences)(value)
        },
      },
    }
  },
  methods: {
    sortReferenceChangedByUser(value) {
      this.sortReference = value
      this.emitValue()
    },
    orderByChangedByUser(index) {
      this.orderDirectionIndex = index
      this.emitValue()
    },
    emitValue() {
      if (this.sortReference === null) {
        this.$emit('value-changed', null)
        return
      }

      const chosenReference = this.allowedSortReferences.find(
        (item) => item.reference === this.sortReference
      )
      this.$emit('value-changed', {
        sort_on: chosenReference.sort_on,
        reference: chosenReference.reference,
        direction: this.orderDirectionOptions[this.orderDirectionIndex].value,
      })
    },
    fieldIconClass(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.iconClass
    },
  },
}
</script>
