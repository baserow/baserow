<template>
  <form @submit.prevent>
    <FormSection
      :title="$t('groupedAggregateRowsDataSourceForm.data')"
      class="margin-bottom-2"
    >
      <FormGroup
        :label="$t('groupedAggregateRowsDataSourceForm.sourceFieldLabel')"
        class="margin-bottom-2"
        small-label
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          v-model="computedTableId"
          :show-search="true"
          fixed-items
          :error="fieldHasErrors('table_id')"
        >
          <DropdownSection
            v-for="database in databases"
            :key="database.id"
            :title="`${database.name} (${database.id})`"
          >
            <DropdownItem
              v-for="table in database.tables"
              :key="table.id"
              :name="table.name"
              :value="table.id"
              :indented="true"
            >
              {{ table.name }}
            </DropdownItem>
          </DropdownSection>
        </Dropdown>
      </FormGroup>
      <FormGroup
        v-if="values.table_id && !fieldHasErrors('table_id')"
        :label="$t('groupedAggregateRowsDataSourceForm.viewFieldLabel')"
        class="margin-bottom-2"
        small-label
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          v-model="v$.values.view_id.$model"
          :show-search="false"
          fixed-items
          :error="fieldHasErrors('view_id')"
        >
          <DropdownItem
            :name="$t('groupedAggregateRowsDataSourceForm.notSelected')"
            :value="null"
            >{{
              $t('groupedAggregateRowsDataSourceForm.notSelected')
            }}</DropdownItem
          >
          <DropdownItem
            v-for="view in tableViews"
            :key="view.id"
            :name="view.name"
            :value="view.id"
          >
            {{ view.name }}
          </DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormSection>
    <FormSection
      v-if="values.table_id && !fieldHasErrors('table_id')"
      :title="$t('groupedAggregateRowsDataSourceForm.series')"
      class="margin-bottom-2"
    >
      <template #title-slot>
        <ButtonText
          icon="iconoir-plus"
          type="secondary"
          :disabled="!canAddSeries || disabled"
          :loading="loading"
          tooltip-position="bottom-left"
          @click="addSeries"
        >
          {{ $t('groupedAggregateRowsDataSourceForm.addSeries') }}
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
        :widget="widget"
        :loading="loading"
        @delete-series="deleteSeries"
        @values-changed="onAggregationSeriesUpdated(index, $event)"
        @series-config-changed="onSeriesConfigUpdated($event)"
      >
      </AggregationSeriesForm>
    </FormSection>
    <AggregationGroupByForm
      v-if="values.table_id && !fieldHasErrors('table_id')"
      :aggregation-group-bys="values.aggregation_group_bys"
      :table-fields="tableFields"
      @value-changed="onGroupByUpdated($event)"
    >
    </AggregationGroupByForm>
    <AggregationSortByForm
      v-if="values.table_id && !fieldHasErrors('table_id')"
      :aggregation-sorts="values.aggregation_sorts"
      :allowed-sort-references="allowedSortReferences"
      @value-changed="onSortByUpdated($event)"
    >
    </AggregationSortByForm>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { required } from '@vuelidate/validators'
import AggregationSeriesForm from '@baserow_premium/dashboard/components/data_source/AggregationSeriesForm'
import AggregationGroupByForm from '@baserow_premium/dashboard/components/data_source/AggregationGroupByForm'
import AggregationSortByForm from '@baserow_premium/dashboard/components/data_source/AggregationSortByForm'
import tableFields from '@baserow/modules/database/mixins/tableFields'

const includesIfSet = (array) => (value) => {
  if (value === null || value === undefined) {
    return true
  }
  return array.includes(value)
}

export default {
  name: 'GroupedAggregateRowsDataSourceForm',
  components: {
    AggregationSeriesForm,
    AggregationGroupByForm,
    AggregationSortByForm,
  },
  mixins: [form, tableFields],
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    widget: {
      type: Object,
      required: true,
    },
    dataSource: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'table_id',
        'view_id',
        'aggregation_series',
        'aggregation_group_bys',
        'aggregation_sorts',
      ],
      values: {
        table_id: null,
        view_id: null,
        aggregation_series: [],
        aggregation_group_bys: [],
        aggregation_sorts: [],
      },
      tableLoading: false,
      skipFirstValuesEmit: true,
    }
  },
  computed: {
    computedTableId: {
      get() {
        return this.v$.values.table_id.$model
      },
      set(tableId) {
        if (tableId !== this.v$.values.table_id.$model) {
          this.v$.values.table_id.$model = tableId
          this.v$.values.view_id.$model = null
          this.values.aggregation_series = [
            { field_id: null, aggregation_type: '' },
          ]
          this.values.aggregation_group_bys = []
          this.values.aggregation_sorts = []

          // reset widget conf
          this.$emit('widget-values-changed', {
            series_config: [],
          })
        }
      },
    },
    integration() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getIntegrationById`
      ](this.dataSource.integration_id)
    },
    databases() {
      return this.integration.context_data.databases
    },
    databaseSelected() {
      return this.databases.find((database) =>
        database.tables.some((table) => table.id === this.values.table_id)
      )
    },
    tables() {
      return this.databases.map((database) => database.tables).flat()
    },
    tableIds() {
      return this.tables.map((table) => table.id)
    },
    tableSelected() {
      return this.tables.find(({ id }) => id === this.values.table_id)
    },
    primaryTableField() {
      return this.tableFields.find((item) => item.primary === true)
    },
    tableFieldIds() {
      return this.tableFields.map((field) => field.id)
    },
    tableViews() {
      return (
        this.databaseSelected?.views.filter(
          (view) => view.table_id === this.values.table_id
        ) || []
      )
    },
    tableViewIds() {
      return this.tableViews.map((view) => view.id)
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
    canAddSeries() {
      return (
        this.values.aggregation_series.length <
        this.$config.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_SERIES
      )
    },
  },
  watch: {
    dataSource: {
      async handler(values) {
        this.setEmitValues(false)
        // Reset the form to set default values
        // again after a different widget is selected
        await this.reset(true)
        // Run form validation so that
        // problems are highlighted immediately
        this.v$.$touch()
        await this.$nextTick()
        this.setEmitValues(true)
      },
      deep: true,
    },
  },
  mounted() {
    this.v$.$touch()
  },
  validations() {
    const self = this
    return {
      values: {
        table_id: {
          required,
          isValidTableId: (value) => {
            const ids = self.tableIds
            return includesIfSet(ids)(value)
          },
        },
        view_id: {
          isValidViewId: (value) => {
            const ids = self.tableViewIds
            return includesIfSet(ids)(value)
          },
        },
      },
    }
  },
  methods: {
    /* Overrides the method in the tableFields mixin */
    getTableId() {
      return this.values.table_id
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
    async addSeries() {
      this.setEmitValues(false)
      this.values.aggregation_series.push({
        field_id: null,
        aggregation_type: '',
      })
      this.$emit('values-changed', {
        aggregation_series: this.values.aggregation_series,
      })
      await this.$nextTick()
      this.setEmitValues(true)
    },
    async deleteSeries(index) {
      this.setEmitValues(false)
      const seriesId = this.values.aggregation_series[index].id

      // Update series
      this.values.aggregation_series.splice(index, 1)
      await this.$nextTick()
      this.$refs.aggregationSeriesForms.forEach((form) => form.reset())
      this.$emit('values-changed', {
        aggregation_series: this.values.aggregation_series,
      })

      // Update series config
      const updatedSeriesConfig = JSON.parse(
        JSON.stringify(this.widget.series_config || [])
      )
      const deleteIndex = updatedSeriesConfig.findIndex(
        (item) => item.series_id === seriesId
      )
      if (deleteIndex >= 0) {
        updatedSeriesConfig.splice(deleteIndex, 1)
        this.$emit('widget-values-changed', {
          series_config: updatedSeriesConfig,
        })
      }

      await this.$nextTick()
      this.setEmitValues(true)
      this.v$.$touch()
    },
    onSeriesConfigUpdated(updatedValues) {
      const updatedSeriesConfig = JSON.parse(
        JSON.stringify(this.widget.series_config || [])
      )
      const index = updatedSeriesConfig.findIndex(
        (item) => item.series_id === updatedValues.series_id
      )
      if (index >= 0) {
        updatedSeriesConfig[index] = updatedValues
      } else {
        updatedSeriesConfig.push(updatedValues)
      }
      this.$emit('widget-values-changed', {
        series_config: updatedSeriesConfig,
      })
    },
    onAggregationSeriesUpdated(index, aggregationSeriesValues) {
      const updatedAggregationSeries = this.values.aggregation_series
      updatedAggregationSeries[index] = aggregationSeriesValues
      this.$emit('values-changed', {
        aggregation_series: updatedAggregationSeries,
      })
    },
    onGroupByUpdated(groupBy) {
      const aggregationGroupBys = []
      if (groupBy !== 'none') {
        aggregationGroupBys.push({
          field_id: groupBy,
        })
      }
      this.$emit('values-changed', {
        aggregation_group_bys: aggregationGroupBys,
      })
    },
    onSortByUpdated(sort) {
      const aggregationSorts = sort !== null ? [sort] : []
      this.$emit('values-changed', {
        aggregation_sorts: aggregationSorts,
      })
    },
  },
}
</script>
