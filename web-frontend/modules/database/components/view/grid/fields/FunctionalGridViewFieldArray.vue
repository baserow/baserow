<template functional>
  <!--  Vue 2 does not support nested importing of components other than this way -->
  <component
    :is="$options.components.FunctionalFormulaArrayItems"
    class="grid-view__cell grid-view-array-field"
    :class="[data.staticClass, data.class]"
    :field="props.field"
    :value="props.value"
    :row="props.row"
    :selected="props.selected"
    v-on="listeners"
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
</template>

<script>
import FunctionalFormulaArrayItems from '@baserow/modules/database/components/formula/array/FunctionalFormulaArrayItems'
import { LINKED_ITEMS_DEFAULT_LOAD_COUNT } from '@baserow/modules/database/constants'

export default {
  name: 'FunctionalGridViewFieldArray',
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
