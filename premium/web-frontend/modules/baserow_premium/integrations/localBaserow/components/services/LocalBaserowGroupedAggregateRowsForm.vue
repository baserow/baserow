<template>
  <form :class="{ 'service-form--small': small }" @submit.prevent>
    <LocalBaserowServiceForm
      :application="application"
      :service-type="serviceType"
      :default-values="defaultValues"
      :enable-integration-picker="enableIntegrationPicker"
      @values-changed="onServiceFormValuesChanged"
    />
    <FormSection
      v-if="values.table_id && !fieldsLoading"
      :title="$t('localBaserowGroupedAggregateRowsForm.series')"
      class="margin-bottom-2"
    >
      <template #title-slot>
        <ButtonText
          icon="iconoir-plus"
          type="secondary"
          :disabled="!canAddSeries"
          tooltip-position="bottom-left"
          @click="addSeries"
        >
          {{ $t('localBaserowGroupedAggregateRowsForm.addSeries') }}
        </ButtonText>
      </template>
      <div class="margin-bottom-2"></div>
      <AggregationSeriesForm
        v-for="(series, index) in values.aggregation_series"
        ref="aggregationSeriesForms"
        :key="index"
        :disabled="fieldsLoading"
        :table-fields="tableFields"
        :aggregation-series="values.aggregation_series"
        :series-index="index"
        :default-values="series"
        @delete-series="deleteSeries"
        @values-changed="onAggregationSeriesUpdated(index, $event)"
      />
    </FormSection>
    <ServiceRefinementForms
      v-if="!fieldsLoading && values.table_id"
      :small="small"
      :values="values"
      :table-fields="tableFields"
      :group-count-override="values.aggregation_group_bys.length"
      :sort-count-override="values.aggregation_sorts.length"
      show-filter
      show-group
      show-sort
    >
      <template #group-form>
        <AggregationGroupByForm
          :aggregation-group-bys="values.aggregation_group_bys"
          :table-fields="tableFields"
          @value-changed="onGroupByUpdated($event)"
        />
      </template>
      <template #sort-form>
        <AggregationSortByForm
          :aggregation-sorts="values.aggregation_sorts"
          :allowed-sort-references="allowedSortReferences"
          @value-changed="onSortByUpdated($event)"
        />
      </template>
    </ServiceRefinementForms>
    <div v-if="fieldsLoading" class="loading-spinner"></div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm.vue'
import ServiceRefinementForms from '@baserow/modules/integrations/localBaserow/components/services/ServiceRefinementForms'
import AggregationSeriesForm from '@baserow_premium/integrations/localBaserow/components/services/AggregationSeriesForm'
import AggregationGroupByForm from '@baserow_premium/integrations/localBaserow/components/services/AggregationGroupByForm'
import AggregationSortByForm from '@baserow_premium/integrations/localBaserow/components/services/AggregationSortByForm'

export default {
  name: 'LocalBaserowGroupedAggregateRowsForm',
  components: {
    LocalBaserowServiceForm,
    ServiceRefinementForms,
    AggregationSeriesForm,
    AggregationGroupByForm,
    AggregationSortByForm,
  },
  mixins: [form, localBaserowService],
  data() {
    return {
      allowedValues: [
        'table_id',
        'view_id',
        'integration_id',
        'filters',
        'filter_type',
        'aggregation_series',
        'aggregation_group_bys',
        'aggregation_sorts',
      ],
      values: {
        table_id: null,
        view_id: null,
        integration_id: null,
        filters: [],
        filter_type: 'AND',
        aggregation_series: [],
        aggregation_group_bys: [],
        aggregation_sorts: [],
      },
    }
  },
  computed: {
    primaryTableField() {
      return this.tableFields.find((item) => item.primary === true)
    },
    canAddSeries() {
      return (
        this.values.aggregation_series.length <
        this.$config.public.baserowPremiumGroupedAggregateServiceMaxSeries
      )
    },
    allowedSortReferences() {
      const seriesSortReferences = this.values.aggregation_series
        .filter(
          (item) =>
            item.field_id &&
            item.aggregation_type &&
            this.getTableFieldById(item.field_id)
        )
        .map((item) => {
          const field = this.getTableFieldById(item.field_id)
          return {
            sort_on: 'SERIES',
            reference: `field_${item.field_id}_${item.aggregation_type}`,
            field,
            name: `${field.name} (${this.getAggregationName(
              item.aggregation_type
            )})`,
          }
        })
      const groupBySortReferences = this.values.aggregation_group_bys.reduce(
        (acc, item) => {
          const field =
            item.field_id === null
              ? this.primaryTableField
              : this.getTableFieldById(item.field_id)

          if (field !== undefined) {
            acc.push({
              sort_on: 'GROUP_BY',
              reference: `field_${field.id}`,
              field,
              name: field.name,
            })
          }

          return acc
        },
        []
      )
      return seriesSortReferences.concat(groupBySortReferences)
    },
  },
  methods: {
    getFormValues(deep = false) {
      const values = Object.assign(
        {},
        this.values,
        this.getChildFormsValues(deep)
      )
      if (Array.isArray(values.aggregation_series)) {
        values.aggregation_series = values.aggregation_series.map((series) => {
          const { id, ...rest } = series
          return id == null ? rest : { id, ...rest }
        })
      }
      return values
    },
    getTableFieldById(fieldId) {
      return this.tableFields.find((tableField) => {
        return tableField.id === fieldId
      })
    },
    getAggregationName(aggregationType) {
      const aggType = this.$registry.get('groupedAggregation', aggregationType)
      return aggType.getName()
    },
    onServiceFormValuesChanged(newValues) {
      const tableChanged =
        'table_id' in newValues && newValues.table_id !== this.values.table_id

      Object.assign(this.values, newValues)

      if (tableChanged) {
        this.values.aggregation_series = [
          { field_id: null, aggregation_type: '' },
        ]
        this.values.aggregation_group_bys = []
        this.values.aggregation_sorts = []
        this.values.filters = []
      }
    },
    addSeries() {
      this.values.aggregation_series.push({
        field_id: null,
        aggregation_type: '',
      })
    },
    async deleteSeries(index) {
      this.values.aggregation_series.splice(index, 1)
      await this.$nextTick()
      if (this.$refs.aggregationSeriesForms) {
        this.$refs.aggregationSeriesForms.forEach((form) => form.reset())
      }
    },
    onAggregationSeriesUpdated(index, aggregationSeriesValues) {
      const cleaned = { ...aggregationSeriesValues }
      if (cleaned.id === null || cleaned.id === undefined) {
        delete cleaned.id
      }
      this.values.aggregation_series.splice(index, 1, cleaned)
    },
    onGroupByUpdated(groupBy) {
      const aggregationGroupBys = []
      if (groupBy !== 'none') {
        aggregationGroupBys.push({ field_id: groupBy })
      }
      this.values.aggregation_group_bys = aggregationGroupBys
    },
    onSortByUpdated(sort) {
      this.values.aggregation_sorts = sort !== null ? [sort] : []
    },
  },
}
</script>
