<template>
  <form @submit.prevent>
    <LocalBaserowServiceForm
      :service-type="serviceType"
      :enable-row-id="enableRowId"
      :application="application"
      :enable-view-picker="false"
      :default-values="defaultValues"
      @table-changed="handleTableChange"
      @values-changed="emitServiceChange($event)"
    ></LocalBaserowServiceForm>
    <div v-if="tableLoading" class="loading-spinner margin-bottom-1"></div>
    <p v-if="values.integration_id && !values.table_id">
      {{ $t('localBaserowUpsertRowServiceForm.noTableSelectedMessage') }}
    </p>
    <FieldMappingsForm
      v-if="!tableLoading"
      v-model="values.field_mappings"
      :fields="writableSchemaFields"
    ></FieldMappingsForm>
    <Alert
      v-if="!tableLoading && service?.table_id && !writableSchemaFields.length"
      type="warning"
    >
      <p>{{ $t('localBaserowUpsertRowServiceForm.noWritableFields') }}</p>
    </Alert>
  </form>
</template>

<script>
import _ from 'lodash'
import FieldMappingsForm from '@baserow/modules/integrations/localBaserow/components/services/FieldMappingsForm'
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  name: 'LocalBaserowUpsertRowServiceForm',
  components: {
    LocalBaserowServiceForm,
    FieldMappingsForm,
  },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
    /**
     * Returns the loading state of the workflow action. Used to
     * determine whether to show the loading spinner in the form.
     */
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    service: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    serviceType: {
      type: Object,
      required: false,
      default: () => ({}),
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
      skipFirstValuesEmit: true,
    }
  },
  computed: {
    /**
     * Returns the writable fields in the schema, which the
     * `FieldMappingForm` can use to display the field mapping options.
     */
    writableSchemaFields() {
      if (
        this.service == null ||
        this.service.schema == null // have service, no table
      ) {
        return []
      }
      const schema = this.service.schema
      const schemaProperties =
        schema.type === 'array' ? schema.items.properties : schema.properties
      return Object.values(schemaProperties)
        .filter(({ metadata }) => metadata && !metadata.read_only)
        .map((prop) => prop.metadata)
    },
  },
  watch: {
    loading: {
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
        const differences = Object.fromEntries(
          Object.entries(newValues).filter(
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
        if (Object.keys(differences).length > 0) {
          this.$emit('values-changed', differences)
        }
      }
    },
  },
}
</script>
