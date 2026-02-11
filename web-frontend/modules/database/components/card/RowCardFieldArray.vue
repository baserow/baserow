<template>
  <div class="card-array__wrapper">
    <FunctionalFormulaArrayItems
      class="card-array"
      :row="row"
      :field="field"
      :value="value"
      :selected="true"
      v-bind="containerAttrs"
      v-on="listenerAttrs"
    >
      <div
        v-if="shouldFetchRow"
        class="array-field__item"
        :class="placeholderClasses"
      >
        <div v-if="isFetchingRow" class="loading"></div>
        <span v-else>...</span>
      </div>
      <slot></slot>
    </FunctionalFormulaArrayItems>
  </div>
</template>

<script>
import FunctionalFormulaArrayItems from '@baserow/modules/database/components/formula/array/FunctionalFormulaArrayItems'
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  height: 22,
  name: 'RowCardFieldArray',
  components: { FunctionalFormulaArrayItems },
  inheritAttrs: false,
  props: {
    row: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    value: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    containerAttrs() {
      const attrs = {}
      Object.keys(this.$attrs).forEach((key) => {
        if (!key.startsWith('on')) {
          attrs[key] = this.$attrs[key]
        }
      })
      return attrs
    },
    listenerAttrs() {
      const attrs = {}
      Object.keys(this.$attrs).forEach((key) => {
        if (key.startsWith('on')) {
          attrs[key] = this.$attrs[key]
        }
      })
      return attrs
    },
    shouldFetchRow() {
      return (
        this.value?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !this.row._?.fullyLoaded
      )
    },
    isFetchingRow() {
      return this.row._?.fetching
    },
    placeholderClasses() {
      return [
        this.containerAttrs.class,
        this.isFetchingRow ? 'array-field__item--loading' : '',
      ]
    },
  },
}
</script>
