<template>
  <FunctionalFormulaArrayItems
    class="grid-view__cell grid-view-array-field"
    :field="field"
    :value="value"
    :row="row"
    :selected="selected"
    v-bind="$attrs"
  >
    <div
      v-if="shouldFetchRow"
      class="array-field__item"
      :class="[$attrs.class, isFetchingRow ? 'array-field__item--loading' : '']"
    >
      <div v-if="isFetchingRow" class="loading"></div>
      <span v-else>...</span>
    </div>
    <slot></slot>
  </FunctionalFormulaArrayItems>
</template>

<script>
import FunctionalFormulaArrayItems from '@baserow/modules/database/components/formula/array/FunctionalFormulaArrayItems'
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  name: 'FunctionalGridViewFieldArray',
  components: { FunctionalFormulaArrayItems },
  inheritAttrs: false,
  props: {
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: Array,
      default: () => [],
    },
    row: {
      type: Object,
      required: true,
    },
    selected: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    shouldFetchRow() {
      return (
        this.value?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !this.row._?.fullyLoaded
      )
    },
    isFetchingRow() {
      return this.row._?.fetching
    },
  },
}
</script>
