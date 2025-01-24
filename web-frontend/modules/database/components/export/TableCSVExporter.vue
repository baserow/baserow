<template>
  <div>
    <div class="row">
      <div class="col col-4">
        <FormGroup
          small-label
          :label="$t('tableCSVExporter.columnSeparatorLabel')"
          required
          class="margin-bottom-2"
        >
          <Dropdown v-model="values.csv_column_separator" :disabled="loading">
            <DropdownItem name="," value=","></DropdownItem>
            <DropdownItem name=";" value=";"></DropdownItem>
            <DropdownItem name="|" value="|"></DropdownItem>
            <DropdownItem name="<tab>" value="tab"></DropdownItem>
            <DropdownItem
              :name="$t('tableCSVExporter.recordSeparator') + ' (30)'"
              value="record_separator"
            ></DropdownItem>
            <DropdownItem
              :name="$t('tableCSVExporter.unitSeparator') + ' (31)'"
              value="unit_separator"
            ></DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
      <div class="col col-8">
        <FormGroup
          small-label
          :label="$t('tableCSVExporter.encodingLabel')"
          required
          class="margin-bottom-2"
        >
          <CharsetDropdown
            v-model="values.export_charset"
            :disabled="loading"
          />
        </FormGroup>
      </div>
    </div>
    <div class="row">
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('tableCSVExporter.includeHeader')"
          required
        >
          <Checkbox v-model="values.csv_include_header" :disabled="loading">{{
            $t('common.yes')
          }}</Checkbox>
        </FormGroup>
      </div>
    </div>
  </div>
</template>

<script>
// Please keep csvColumnSeparator values in sync with
// src/baserow/contrib/database/api/export/serializers.py:SUPPORTED_CSV_COLUMN_SEPARATORS
import CharsetDropdown from '@baserow/modules/core/components/helpers/CharsetDropdown'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'TableCSVExporter',
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
        csv_include_header: true,
        export_charset: 'utf-8',
        csv_column_separator: ',',
      },
    }
  },
}
</script>
