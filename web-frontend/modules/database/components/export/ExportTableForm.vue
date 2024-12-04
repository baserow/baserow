<template>
  <form @submit.prevent="submit">
    <div class="row">
      <div class="col col-12">
        <FormGroup
          small-label
          :label="$t('exportTableForm.viewLabel')"
          required
          class="margin-bottom-2"
        >
          <ExportTableDropdown
            v-model="v$.view_id.$model"
            :views="viewsWithExporterTypes"
            :loading="loading"
            @input="values.exporter_type = firstExporterType"
          ></ExportTableDropdown>
        </FormGroup>

        <ExporterTypeChoices
          v-model="v$.exporter_type.$model"
          :exporter-types="exporterTypes"
          :loading="loading"
          :database="database"
          class="margin-bottom-2"
        ></ExporterTypeChoices>
        <div v-if="v$.exporter_type.$error" class="error">
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
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'

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
  },
  data() {
    return {
      values: {
        view_id: this.view === null ? null : this.view.id,
        exporter_type: null,
      },
      v$: null,
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
          (exporterType) => exporterType.type === this.v$.exporter_type.$model
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
      if (!this.v$.exporter_type.$model) {
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
    const values = reactive({
      exporter_type: this.firstExporterType,
      view_id: this.view === null ? null : this.view.id,
    })

    const rules = computed(() => ({
      exporter_type: { required },
      view_id: {},
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
