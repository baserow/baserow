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
        <Dropdown v-model="values.table_id" :show-search="true" fixed-items>
          <DropdownItem
            v-for="table in tables"
            :key="table.id"
            :name="table.name"
            :value="table.id"
          >
            {{ table.name }}
          </DropdownItem>
        </Dropdown>
      </FormGroup>
      <FormGroup
        v-if="values.table_id"
        :label="$t('aggregateRowsDataSourceForm.viewFieldLabel')"
        class="margin-bottom-2"
        small-label
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown v-model="values.view_id" :show-search="false" fixed-items>
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
        v-if="values.table_id"
        class="margin-bottom-2"
        small-label
        :label="$t('aggregateRowsDataSourceForm.aggregationFieldLabel')"
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          v-model="values.field_id"
          :disabled="tableFields.length === 0"
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
        v-if="values.field_id"
        small-label
        :label="$t('aggregateRowsDataSourceForm.aggregationTypeLabel')"
        required
        horizontal
        horizontal-narrow
      >
        <Dropdown
          v-model="values.aggregation_type"
          :disabled="!values.field_id"
        >
          <DropdownItem
            v-for="viewAggregation in viewAggregationTypes"
            :key="viewAggregation.getType()"
            :name="viewAggregation.getName()"
            :value="viewAggregation.getType()"
          >
          </DropdownItem>
        </Dropdown>
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { required } from 'vuelidate/lib/validators'

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
      emitValuesOnReset: false,
    }
  },
  computed: {
    integration() {
      return this.$store.getters['dashboardApplication/getIntegrationById'](
        this.dataSource.integration_id
      )
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
  },
  watch: {
    dataSource(value) {
      this.reset(true)
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

          // FIXME: currently only applied when changing tables but
          // aggregation type won't be corrected when changing field

          if (
            !this.tableFields.some((field) => field.id === this.values.field_id)
          ) {
            this.values.field_id = this.tableFields[0].id
          }

          if (
            !this.tableViews.some((view) => view.id === this.values.view_id)
          ) {
            this.values.view_id = null
          }

          if (
            !this.viewAggregationTypes.some(
              (agg) => agg.getType() === this.values.aggregation_type
            )
          ) {
            this.values.aggregation_type =
              this.viewAggregationTypes[0].getType()
          }
        }
      },
      immediate: false,
    },
  },
  validations() {
    return {
      values: {
        table_id: { required },
        view_id: { isValidViewId: includesIfSet(this.tableViewIds) },
        field_id: { required, isValidFieldId: includes(this.tableFieldIds) },
        aggregation_type: {
          required,
          isValidAggregationType: includes(this.aggregationTypeNames),
        },
      },
    }
  },
  methods: {
    fieldIconClass(field) {
      const fieldType = this.$registry.get('field', field.type)
      return fieldType.iconClass
    },
  },
  // methods: {
  // TODO:
  //   /**
  //    * Given an array of objects containing a `field` property (e.g. the data
  //    * source filters or sortings arrays), this method will return a new array
  //    * containing only the objects where the field is part of the schema, so,
  //    * untrashed.
  //    *
  //    * @param {Array} value - The array of objects to filter.
  //    * @returns {Array} - The filtered array.
  //    */
  //   excludeTrashedFields(value) {
  //     const localBaserowFieldIds = this.tableFields.map(({ id }) => id)
  //     return value.filter(({ field }) => localBaserowFieldIds.includes(field))
  //   },
  // },
}
</script>
