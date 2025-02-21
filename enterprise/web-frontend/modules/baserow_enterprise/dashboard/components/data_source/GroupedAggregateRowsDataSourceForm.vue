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
          v-model="values.table_id"
          :show-search="true"
          fixed-items
          :error="fieldHasErrors('table_id')"
          @change="v$.values.table_id.$touch"
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
          v-model="values.view_id"
          :show-search="false"
          fixed-items
          :error="fieldHasErrors('view_id')"
          @change="v$.values.view_id.$touch"
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
        <ButtonText icon="iconoir-plus" type="secondary" @click="addSeries">{{
          $t('groupedAggregateRowsDataSourceForm.addSeries')
        }}</ButtonText>
      </template>
      <div class="margin-bottom-2"></div>
      <AggregationSeriesForm
        v-for="(series, index) in values.aggregation_series"
        :key="index"
        :table-fields="tableFields"
        :series-index="index"
        :default-values="series"
        @delete-series="deleteSeries"
        @values-changed="onAggregationSeriesUpdated(index, $event)"
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
      :aggregation-sorts="values.sortings"
      :allowed-sort-fields="allowedSortFields"
      @value-changed="onSortByUpdated($event)"
    >
    </AggregationSortByForm>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { required } from '@vuelidate/validators'
import AggregationSeriesForm from '@baserow_enterprise/dashboard/components/data_source/AggregationSeriesForm'
import AggregationGroupByForm from '@baserow_enterprise/dashboard/components/data_source/AggregationGroupByForm'
import AggregationSortByForm from '@baserow_enterprise/dashboard/components/data_source/AggregationSortByForm'

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
  mixins: [form],
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
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'table_id',
        'view_id',
        'aggregation_series',
        'aggregation_group_bys',
        'sortings',
      ],
      values: {
        table_id: null,
        view_id: null,
        aggregation_series: [],
        aggregation_group_bys: [],
        sortings: [],
      },
      tableLoading: false,
      databaseSelectedId: null,
      emitValuesOnReset: false,
    }
  },
  computed: {
    integration() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getIntegrationById`
      ](this.dataSource.integration_id)
    },
    databases() {
      return this.integration.context_data.databases
    },
    databaseSelected() {
      return this.databases.find(
        (database) => database.id === this.databaseSelectedId
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
    tableFields() {
      return this.tableSelected?.fields || []
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
    allowedSortFields() {
      console.log('updating allowed sort fields')
      const seriesFieldIds = this.values.aggregation_series.map(
        (item) => item.field_id
      )
      const groupByFieldIds = this.values.aggregation_group_bys.map(
        (item) => item.field_id
      )
      const allowedFieldIds = seriesFieldIds.concat(groupByFieldIds)
      return this.tableFields.filter((item) => {
        return allowedFieldIds.includes(item.id)
      })
    },
  },
  watch: {
    dataSource: {
      handler(values) {
        // Reset the form to set default values
        // again after a different widget is selected
        this.reset(true)
        // Run form validation so that
        // problems are highlighted immediately
        this.v$.$validate(true)
      },
      deep: true,
    },
    'values.table_id': {
      handler(tableId) {
        if (tableId !== null) {
          const databaseOfTableId = this.databases.find((database) =>
            database.tables.some((table) => table.id === tableId)
          )
          if (databaseOfTableId) {
            this.databaseSelectedId = databaseOfTableId.id
          }

          // If the values are not changed by the user
          // we don't want to continue with preselecting
          // default values
          if (tableId === this.defaultValues.table_id) {
            return
          }

          if (
            !this.tableViews.some((view) => view.id === this.values.view_id)
          ) {
            this.values.view_id = null
          }
        }
      },
      immediate: true,
    },
  },
  mounted() {
    this.v$.$validate(true)
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
    addSeries() {
      this.values.aggregation_series.push({
        field_id: null,
        aggregation_type: '',
      })
    },
    deleteSeries(index) {
      this.values.aggregation_series.splice(index, 1)
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
    onSortByUpdated(sortBy) {
      const aggregationSorts = sortBy.field !== null ? [sortBy] : []
      this.$emit('values-changed', {
        sortings: aggregationSorts,
      })
    },
  },
}
</script>
