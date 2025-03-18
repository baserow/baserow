<template>
  <form @submit.prevent>
    <LocalBaserowServiceForm
      :enable-row-id="enableRowId"
      :default-values="defaultValues"
      @table-changed="handleTableChange"
      @values-changed="emitServiceChange($event)"
    ></LocalBaserowServiceForm>
    <div v-if="tableLoading" class="loading-spinner margin-bottom-1"></div>
    <p v-if="values.integration_id && !values.table_id">
      {{ $t('upsertRowWorkflowActionForm.noTableSelectedMessage') }}
    </p>
    <FieldMappingForm
      v-if="!tableLoading"
      v-model="values.field_mappings"
      :fields="getWritableSchemaFields"
    ></FieldMappingForm>
  </form>
</template>

<script>
import _ from 'lodash'
import FieldMappingForm from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingForm'
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  name: 'LocalBaserowUpsertRowServiceForm',
  components: {
    LocalBaserowServiceForm,
    FieldMappingForm,
  },
  mixins: [form],
  props: {
    workflowAction: {
      type: Object,
      required: false,
      default: null,
    },
    enableRowId: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: ['field_mappings'],
      values: {
        field_mappings: [],
      },
      state: null,
      tableLoading: false,
    }
  },
  computed: {
    /**
     * Returns the loading state of the workflow action. Used to
     * determine whether to show the loading spinner in the water.
     */
    workflowActionLoading() {
      return this.$store.getters['workflowAction/getLoading'](
        this.workflowAction
      )
    },
    /**
     * Returns the writable fields in the schema, which the
     * `FieldMappingForm` can use to display the field mapping options.
     */
    getWritableSchemaFields() {
      if (
        this.workflowAction.service == null ||
        this.workflowAction.service.schema == null // have service, no table
      ) {
        return []
      }
      const schema = this.workflowAction.service.schema
      const schemaProperties =
        schema.type === 'array' ? schema.items.properties : schema.properties
      return Object.values(schemaProperties)
        .filter(({ metadata }) => metadata && !metadata.read_only)
        .map((prop) => prop.metadata)
    },
  },
  watch: {
    workflowActionLoading: {
      handler(value) {
        if (!value) {
          this.tableLoading = false
        }
      },
    },
  },
  methods: {
    /**
     * When `LocalBaserowServiceForm` informs us that the table
     * has changed, we'll flag our `tableLoading` boolean as true.
     * We want to display a loading spinner between the `table_id`
     * changing, and the `field_mappings` being loaded.
     */
    handleTableChange(newValue) {
      this.tableLoading = true
    },
    /**
     * When `LocalBaserowServiceForm` informs us that service specific
     * values have changed, we want to determine what has changed and
     * emit the new values to the parent component.
     */
    emitServiceChange(newValues) {
      if (this.isFormValid()) {
        const updated = { ...this.defaultValues, ...newValues }
        const differences = Object.fromEntries(
          Object.entries(updated).filter(
            ([key, value]) => !_.isEqual(value, this.defaultValues[key])
          )
        )
        // If the `table_id` has changed, we'll reset the `field_mappings`
        // to an empty array. We update both the values and the differences
        // for different reasons: the former so that a subsequent change don't
        // stack up, and the latter so that the HTTP request which is triggered
        // due to the changes in `differences` don't include the old field mappings.
        if (differences.table_id) {
          this.values.field_mappings = []
          differences.field_mappings = []
        }
        this.$emit('values-changed', differences)
      }
    },
  },
}
</script>
