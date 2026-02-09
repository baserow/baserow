<template>
  <FormGroup
    small-label
    :label="$t('exporterTypeChoices.formatLabel')"
    required
  >
    <ul class="choice-items">
      <ExporterTypeChoice
        v-for="exporterType in exporterTypes"
        :key="exporterType.type"
        :exporter-type="exporterType"
        :active="modelValue !== null && modelValue === exporterType.type"
        :disabled="loading"
        :database="database"
        @selected="switchToExporterType(exporterType.type)"
      >
      </ExporterTypeChoice>
    </ul>
  </FormGroup>
  <!-- <div v-if="exporterTypes.length > 0" class="control">
    <label class="control__label">{{
      $t('exporterTypeChoices.formatLabel')
    }}</label>
    <div class="control__elements">
      <ul class="choice-items">
        <ExporterTypeChoice
          v-for="exporterType in exporterTypes"
          :key="exporterType.type"
          :exporter-type="exporterType"
          :active="value !== null && value === exporterType.type"
          :disabled="loading"
          :database="database"
          @selected="switchToExporterType(exporterType.type)"
        >
        </ExporterTypeChoice>
      </ul>
    </div>
  </div> -->
</template>

<script>
import ExporterTypeChoice from '@baserow/modules/database/components/export/ExporterTypeChoice'

export default {
  name: 'ExporterTypeChoices',
  components: { ExporterTypeChoice },
  props: {
    database: {
      type: Object,
      required: true,
    },
    exporterTypes: {
      required: true,
      type: Array,
    },
    modelValue: {
      required: false,
      type: String,
      default: null,
    },
    loading: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['update:modelValue'],
  methods: {
    switchToExporterType(exporterType) {
      if (this.loading) {
        return
      }

      this.$emit('update:modelValue', exporterType)
    },
  },
}
</script>
