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
      // Null until the first fetch resolves, so the form keeps deriving its
      // mappings from a saved service's schema in the meantime.
      mappableFields: null,
      fieldsLoading: false,
      // Bumped per fetch, so a response overtaken by a newer one is dropped
      // rather than left describing a table that is no longer selected.
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
        // Nothing is saved when the table changes, so the form must not raise
        // a spinner of its own: only `loading` above can lower one, and it
        // never moves when the table is re-picked rather than changed.
        props.savesOnTableChange = false
      }
      return props
    },
    selectedTableId() {
      return this.values.service?.table_id || null
    },
    /**
     * A button field has no integration to source a table list from, so the
     * choice is every database in the field's own workspace. The field's own
     * database is included on purpose: a button acting on its own table is
     * legitimate.
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
     * The form derives its mappings from the service schema, which only a
     * saved service carries. This editor buffers its changes, so a new action
     * has none and the form would wrongly report no writable fields.
     */
    async fetchMappableFields(tableId) {
      if (!this.supportsFieldMappings) {
        return
      }
      // Taken before the await, so anything already in flight is superseded.
      const token = ++this.fetchToken
      if (tableId === null) {
        this.mappableFields = null
        // Nothing worth waiting for is left, and the fetch this replaced will
        // not lower the spinner itself now that its token is stale.
        this.fieldsLoading = false
        return
      }
      this.fieldsLoading = true
      try {
        const { data } = await FieldService(this.$client).fetchAll(tableId)
        if (token !== this.fetchToken) {
          return
        }
        // The same filter the schema applies.
        this.mappableFields = data.filter((field) => !field.read_only)
      } catch (error) {
        if (token !== this.fetchToken) {
          return
        }
        this.mappableFields = []
        notifyIf(error, 'field')
      } finally {
        // Only the newest fetch owns the spinner: an overtaken one lowering it
        // would uncover the previous table's mappings mid flight.
        if (token === this.fetchToken) {
          this.fieldsLoading = false
        }
      }
    },
  },
}
</script>
