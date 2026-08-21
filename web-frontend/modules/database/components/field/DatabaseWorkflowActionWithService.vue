<template>
  <component
    :is="serviceType.formComponent"
    v-bind="formProps"
    @values-changed="values.service = { ...defaultValues.service, ...$event }"
  />
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import FieldService from '@baserow/modules/database/services/field'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

export default {
  name: 'DatabaseWorkflowActionWithService',
  mixins: [form],
  inject: {
    // The sub-form collects these so the data explorer can describe what an
    // unsaved action will return.
    registerTableFields: { from: 'registerTableFields', default: null },
  },
  props: {
    workflowAction: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      allowedValues: ['service'],
      values: {
        service: {},
      },
      // Null until the first fetch, so the form keeps using the saved schema.
      mappableFields: null,
      fieldsLoading: false,
      // Bumped per fetch, so an overtaken response is dropped.
      fetchToken: 0,
    }
  },
  computed: {
    workflowActionType() {
      return this.$registry.get(
        'databaseWorkflowActionType',
        this.workflowAction.type
      )
    },
    serviceType() {
      return this.workflowActionType.serviceType
    },
    // Delete row has no field mappings, so its form takes neither prop.
    supportsFieldMappings() {
      return this.workflowActionType.mapsFields
    },
    formProps() {
      const props = {
        application: this.database,
        service: this.defaultValues.service,
        serviceType: this.serviceType,
        databases: this.workspaceDatabases,
        defaultValues: this.defaultValues.service,
      }
      if (this.supportsFieldMappings) {
        props.mappableFields = this.mappableFields
        props.loading = this.fieldsLoading
        // Nothing is saved on a table change here, so the form must not raise
        // a spinner that only its `loading` prop can lower.
        props.savesOnTableChange = false
      }
      return props
    },
    selectedTableId() {
      return this.values.service?.table_id || null
    },
    /**
     * A button field has no integration to source a table list from, so every
     * database in the field's workspace is offered, its own included.
     */
    workspaceDatabases() {
      return this.$store.getters['application/getAllOfWorkspace'](
        this.database.workspace
      ).filter(
        (application) => application.type === DatabaseApplicationType.getType()
      )
    },
  },
  watch: {
    selectedTableId: {
      immediate: true,
      handler(tableId) {
        this.fetchMappableFields(tableId)
      },
    },
  },
  methods: {
    /**
     * The form normally derives its mappings from the service schema, which
     * only a saved service carries. This editor buffers its changes, so a new
     * action has no schema and needs the fields fetched for it.
     */
    async fetchMappableFields(tableId) {
      if (!this.supportsFieldMappings) {
        return
      }
      // Taken before the await, so anything already in flight is superseded.
      const token = ++this.fetchToken
      if (tableId === null) {
        this.mappableFields = null
        // The superseded fetch will not lower the spinner now that its token
        // is stale.
        this.fieldsLoading = false
        return
      }
      this.fieldsLoading = true
      try {
        const { data } = await FieldService(this.$client).fetchAll(tableId)
        if (token !== this.fetchToken) {
          return
        }
        // The same filter the schema applies. Unfiltered for the explorer,
        // which can read a created row's read only fields.
        this.mappableFields = data.filter((field) => !field.read_only)
        this.registerTableFields?.(tableId, data)
      } catch (error) {
        if (token !== this.fetchToken) {
          return
        }
        this.mappableFields = []
        notifyIf(error, 'field')
      } finally {
        // Only the newest fetch owns the spinner, or an overtaken one
        // uncovers the previous table's mappings mid flight.
        if (token === this.fetchToken) {
          this.fieldsLoading = false
        }
      }
    },
  },
}
</script>
