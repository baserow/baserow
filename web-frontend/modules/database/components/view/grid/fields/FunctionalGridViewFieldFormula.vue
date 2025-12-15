<template>
  <component
    :is="componentType"
    v-if="componentType"
    :row="row"
    :field="field"
    :value="value"
  ></component>
  <div v-else class="grid-view__cell cell-error">Unknown Field Type</div>
</template>
<script>
import FunctionalGridViewFieldBoolean from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldBoolean'
import FunctionalGridViewFieldDate from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldDate'
import FunctionalGridViewFieldNumber from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldNumber'
import FunctionalGridViewFieldText from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewFieldText'
import FunctionalGridViewSingleFile from '@baserow/modules/database/components/view/grid/fields/FunctionalGridViewSingleFile'

export default {
  name: 'FunctionalGridViewFieldFormula',
  components: {
    FunctionalGridViewFieldDate,
    FunctionalGridViewFieldText,
    FunctionalGridViewFieldBoolean,
    FunctionalGridViewFieldNumber,
    FunctionalGridViewSingleFile,
  },
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
      type: null,
      default: null,
    },
  },
  computed: {
    componentType() {
      if (!this.$registry) {
        return null
      }
      const formulaType = this.$registry.get(
        'formula_type',
        this.field.formula_type
      )
      return formulaType.getFunctionalGridViewFieldComponent()
    },
  },
}
</script>
