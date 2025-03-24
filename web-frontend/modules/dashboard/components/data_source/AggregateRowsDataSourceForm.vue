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
        :label="$t('aggregateRowsDataSourceForm.viewFieldLabel')"
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
          :disabled="fieldsLoading"
          :error="fieldHasErrors('view_id')"
          @change="v$.values.view_id.$touch"
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
          v-model="values.field_id"
          :disabled="tableFields.length === 0 || fieldsLoading"
          :error="fieldHasErrors('field_id')"
          @change="v$.values.field_id.$touch"
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
          v-model="values.aggregation_type"
          :error="fieldHasErrors('aggregation_type')"
          :disabled="fieldsLoading"
          @change="v$.values.aggregation_type.$touch"
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
      databaseSelectedId: null,
      skipFirstValuesEmit: true,
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

          if (
            !this.tableFields.some((field) => field.id === this.values.field_id)
          ) {
            if (this.tableFields.length > 0) {
              this.values.field_id = this.tableFields[0].id
            }
          }
        }
      },
      immediate: true,
    },
    'values.field_id': {
      handler(fieldId) {
        if (fieldId !== null) {
          if (
            !this.viewAggregationTypes.some(
              (agg) => agg.getType() === this.values.aggregation_type
            )
          ) {
            if (this.viewAggregationTypes.length > 0) {
              this.values.aggregation_type =
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
