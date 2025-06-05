<template>
  <div class="control__elements">
    <FunctionalFormulaArrayItems
      class="row-edit-array-field"
      :row="row"
      :field="field"
      :value="value"
      :selected="true"
    >
      <div
        v-if="shouldFetchRow"
        class="array-field__item"
        :class="{ 'array-field__item--loading': row._?.fetching }"
      >
        <div v-if="row._?.fetching" class="loading"></div>
        <span v-else>...</span>
      </div>
    </FunctionalFormulaArrayItems>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import FunctionalFormulaArrayItems from '@baserow/modules/database/components/formula/array/FunctionalFormulaArrayItems'
import arrayField from '@baserow/modules/database/mixins/arrayField'

export default {
  name: 'RowEditFieldArray',
  components: {
    FunctionalFormulaArrayItems,
  },
  mixins: [rowEditField, arrayField],
}
</script>
