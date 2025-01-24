<template>
  <div>
    <div class="row">
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('tableExcelExporter.includeHeader')"
          required
        >
          <Checkbox v-model="values.excel_include_header" :disabled="loading">{{
            $t('common.yes')
          }}</Checkbox>
        </FormGroup>
      </div>
    </div>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'TableExcelExporter',
  mixins: [form],
  props: {
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      values: {
        excel_include_header: true,
      },
    }
  },
}
</script>
