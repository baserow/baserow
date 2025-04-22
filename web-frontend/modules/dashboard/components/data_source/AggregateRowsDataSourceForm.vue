<template>
  <form @submit.prevent>
    <FormSection
      :title="$t('aggregateRowsDataSourceForm.data')"
      class="margin-bottom-2"
    >
      <FormGroup
        :label="$t('aggregateRowsDataSourceForm.sourceFieldLabel')"
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
        :label="$t('aggregateRowsDataSourceForm.viewFieldLabel')"
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
          :disabled="fieldsLoading"
          :error="fieldHasErrors('view_id')"
        >
          <DropdownItem
            :name="$t('aggregateRowsDataSourceForm.notSelected')"
            :value="null"
            >{{ $t('aggregateRowsDataSourceForm.notSelected') }}</DropdownItem
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
      <FormGroup
        v-if="values.table_id && !fieldHasErrors('table_id')"
        class="margin-bottom-2"
        small-label
        :label="$t('aggregateRowsDataSourceForm.aggregationFieldLabel')"
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          v-model="v$.values.field_id.$model"
          :disabled="tableFields.length === 0 || fieldsLoading"
          :error="fieldHasErrors('field_id')"
        >
          <DropdownItem
            v-for="field in tableFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
            :icon="fieldIconClass(field)"
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
      <FormGroup
        v-if="!fieldHasErrors('field_id')"
        small-label
        :label="$t('aggregateRowsDataSourceForm.aggregationTypeLabel')"
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          v-model="v$.values.aggregation_type.$model"
          :error="fieldHasErrors('aggregation_type')"
          :disabled="fieldsLoading"
        >
          <DropdownItem
            v-for="viewAggregation in viewAggregationTypes"
            :key="viewAggregation.getType()"
            :name="viewAggregation.getName()"
            :value="viewAggregation.getType()"
            :disabled="
              unsupportedAggregationTypes.includes(viewAggregation.getType())
            "
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { required } from '@vuelidate/validators'
import tableFields from '@baserow/modules/database/mixins/tableFields'

const includes = (array) => (value) => {
  return array.includes(value)
}

const includesIfSet = (array) => (value) => {
  if (value === null || value === undefined) {
    return true
  }
  return array.includes(value)
}

export default {
  name: 'AggregateRowsDataSourceForm',
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
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['table_id', 'view_id', 'field_id', 'aggregation_type'],
      values: {
        table_id: null,
        view_id: null,
        field_id: null,
        aggregation_type: 'sum',
      },
      tableLoading: false,
      skipFirstValuesEmit: true,
      tableIdHasChanged: false,
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
          this.tableIdHasChanged = true
          this.v$.values.view_id.$model = null
          this.v$.values.field_id.$model = null
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
    viewAggregationTypes() {
      const selectedField = this.tableFields.find(
        (field) => field.id === this.values.field_id
      )
      if (!selectedField) return []
      return this.$registry
        .getOrderedList('viewAggregation')
        .filter((agg) => agg.fieldIsCompatible(selectedField))
    },
    aggregationTypeNames() {
      return this.viewAggregationTypes.map((aggType) => aggType.getType())
    },
    unsupportedAggregationTypes() {
      return this.$registry.get('service', 'local_baserow_aggregate_rows')
        .unsupportedAggregationTypes
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
    fieldsLoading(loading) {
      if (this.tableIdHasChanged && !loading) {
        if (this.tableFields.length > 0) {
          this.v$.values.field_id.$model = this.tableFields[0].id
        }
        this.tableIdHasChanged = false
      }
    },
    'values.field_id': {
      handler(fieldId) {
        if (fieldId !== null) {
          if (
            !this.viewAggregationTypes.some(
              (agg) => agg.getType() === this.v$.values.aggregation_type.$model
            )
          ) {
            if (this.viewAggregationTypes.length > 0) {
              this.v$.values.aggregation_type.$model =
                this.viewAggregationTypes[0].getType()
            }
          }
        }
      },
      immediate: false,
    },
  },
  mounted() {
    this.v$.$validate()
  },
  validations() {
    const self = this
    return {
      values: {
        table_id: {
          required,
          isValidTableId: (value) => {
            const ids = self.tableIds
            return includes(ids)(value)
          },
        },
        view_id: {
          isValidViewId: (value) => {
            const ids = self.tableViewIds
            return includesIfSet(ids)(value)
          },
        },
        field_id: {
          required,
          isValidFieldId: (value) => {
            const ids = self.tableFieldIds
            return includes(ids)(value)
          },
        },
        aggregation_type: {
          required,
          isValidAggregationType: (value) => {
            const types = self.aggregationTypeNames
            return includes(types)(value)
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
    fieldIconClass(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.iconClass
    },
  },
}
</script>
