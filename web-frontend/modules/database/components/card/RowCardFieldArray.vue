<template functional>
  <div class="card-array__wrapper">
    <component
      :is="$options.components.FunctionalFormulaArrayItems"
      class="card-array"
      :class="data.staticClass || ''"
      :row="props.row"
      :field="props.field"
      :value="props.value"
      :selected="true"
    >
      <div
        v-if="$options.methods.shouldFetchRow(props)"
        class="array-field__item"
        :class="[
          data.staticClass,
          data.class,
          $options.methods.isFetchingRow(props)
            ? 'array-field__item--loading'
            : '',
        ]"
      >
        <div v-if="$options.methods.isFetchingRow(props)" class="loading"></div>
        <span v-else>...</span>
      </div>
      <slot></slot>
    </component>
  </div>
</template>

<script>
import FunctionalFormulaArrayItems from '@baserow/modules/database/components/formula/array/FunctionalFormulaArrayItems'
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  height: 22,
  name: 'RowCardFieldArray',
  components: { FunctionalFormulaArrayItems },
  methods: {
    shouldFetchRow(props) {
      return (
        props.value?.length === LINKED_ITEMS_DEFAULT_LOAD_COUNT &&
        !props.row._?.fullyLoaded
      )
    },
    isFetchingRow(props) {
      return props.row._?.fetching
    },
  },
}
</script>
