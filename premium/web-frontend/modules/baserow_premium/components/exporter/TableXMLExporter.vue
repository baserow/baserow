<template>
  <div>
    <div class="row">
      <div class="col col-12">
        <FormGroup
          :label="$t('tableXMLExporter.encoding')"
          required
          small-label
          class="margin-bottom-2"
        >
          <CharsetDropdown v-model="values.export_charset" :disabled="loading">
          </CharsetDropdown>
        </FormGroup>
      </div>
    </div>
    <div class="row">
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('exportTableForm.includeRowId')"
          required
        >
          <Checkbox v-model="values.include_row_id" :disabled="loading">{{
            $t('common.yes')
          }}</Checkbox>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('exportTableForm.includePrimaryField')"
          required
        >
          <Checkbox
            v-model="values.include_primary_field"
            :disabled="loading"
            >{{ $t('common.yes') }}</Checkbox
          >
        </FormGroup>
      </div>
    </div>
  </div>
</template>

<script>
import CharsetDropdown from '@baserow/modules/core/components/helpers/CharsetDropdown'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'TableXMLExporter',
  components: { CharsetDropdown },
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
        export_charset: 'utf-8',
        include_row_id: true,
        include_primary_field: true,
      },
    }
  },
}
</script>
