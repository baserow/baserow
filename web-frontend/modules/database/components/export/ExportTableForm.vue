<template>
  <form @submit.prevent="submit">
    <div class="row">
      <div class="col col-12">
        <FormGroup
          v-if="enableViewsDropdown"
          small-label
          :label="$t('exportTableForm.viewLabel')"
          required
          class="margin-bottom-2"
        >
          <ExportTableDropdown
            v-model="values.view_id"
            :views="viewsWithExporterTypes"
            :loading="loading"
            @input="values.exporter_type = firstExporterType"
          ></ExportTableDropdown>
        </FormGroup>

        <ExporterTypeChoices
          v-model="values.exporter_type"
          :exporter-types="exporterTypes"
          :loading="loading"
          :database="database"
          class="margin-bottom-2"
        ></ExporterTypeChoices>
        <div v-if="v$.values.exporter_type.$error" class="error">
          {{ $t('exportTableForm.typeError') }}
        </div>
      </div>
    </div>
    <component
      :is="exporterComponent"
      :loading="loading"
      @values-changed="$emit('values-changed', values)"
    />
    <slot :filename="exportFilename"></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import viewTypeHasExporterTypes from '@baserow/modules/database/utils/viewTypeHasExporterTypes'

import ExportTableDropdown from '@baserow/modules/database/components/export/ExportTableDropdown'
import ExporterTypeChoices from '@baserow/modules/database/components/export/ExporterTypeChoices'

export default {
  name: 'ExportTableForm',
  components: {
    ExporterTypeChoices,
    ExportTableDropdown,
  },
  mixins: [form],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: false,
      default: null,
    },
    views: {
      type: Array,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
    enableViewsDropdown: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  setup() {
    const values = reactive({
      values: {
        view_id: null,
        exporter_type: null,
      },
    })
    const rules = {
      values: {
        exporter_type: {},
        view_id: {},
      },
    }
    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
    }
  },
  computed: {
    viewsWithExporterTypes() {
      return this.views.filter((view) =>
        viewTypeHasExporterTypes(view.type, this.$registry)
      )
    },
    selectedView() {
      return this.views.find((view) => view.id === this.values.view_id) || null
    },
    selectedExporter() {
      return (
        this.exporterTypes.find(
          (exporterType) => exporterType.type === this.values.exporter_type
        ) || null
      )
    },
    exporterTypes() {
      const types = Object.values(this.$registry.getAll('exporter'))
      return types.filter((exporterType) => {
        if (this.selectedView !== null) {
          return exporterType
            .getSupportedViews()
            .includes(this.selectedView.type)
        } else {
          return exporterType.getCanExportTable()
        }
      })
    },
    firstExporterType() {
      return this.exporterTypes.length > 0 ? this.exporterTypes[0].type : null
    },
    exporterComponent() {
      if (!this.values.exporter_type) {
        return null
      }

      return this.selectedExporter.getFormComponent()
    },
    exportFilename() {
      return `export - ${this.table.name}${
        this.selectedView ? ` - ${this.selectedView.name}` : ''
      }.${this.selectedExporter?.getFileExtension()}`
    },
  },
  created() {
    this.values.exporter_type = this.firstExporterType
    this.values.view_id = this.view === null ? null : this.view.id
  },
}
</script>
