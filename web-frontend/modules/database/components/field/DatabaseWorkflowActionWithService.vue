<template>
  <div>
    <component
      :is="serviceType.formComponent"
      v-bind="formProps"
      @values-changed="values.service = { ...defaultValues.service, ...$event }"
    />
    <div v-if="capturesSampleData" class="button-field-action-form__payload">
      <SampleDataViewer
        v-if="sampleData"
        :sample-data="sampleData"
        :is-error="capturedNothing"
        :modal-title="
          $t('databaseWorkflowActionWithService.payloadModalTitle', {
            actionLabel: workflowActionType.label,
          })
        "
        :modal-subtitle="
          $t('databaseWorkflowActionWithService.payloadModalSubTitle')
        "
      />
      <Alert v-else type="info-neutral" class="margin-bottom-0">
        <p>{{ $t('databaseWorkflowActionWithService.nothingCapturedYet') }}</p>
      </Alert>
    </div>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import SampleDataViewer from '@baserow/modules/core/components/SampleDataViewer'
import FieldService from '@baserow/modules/database/services/field'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { FIELDS_UNAVAILABLE } from '@baserow/modules/database/utils/buttonField'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

// A database has no single entry point the way a builder does, so its
// integrations are fetched the first time an action asks for them. Several
// actions of one field mount at once, so the request in flight is shared,
// and the entry is dropped once it settles: whether they have been loaded is
// remembered on the application itself, the way the builder and automation
// do it, so a refetch that replaces the object asks again.
const inFlight = new Map()

async function fetchIntegrationsOnce(store, database) {
  if (database._integrationsLoadedOnce) {
    return
  }
  if (!inFlight.has(database.id)) {
    inFlight.set(
      database.id,
      store
        .dispatch('integration/fetch', { application: database })
        .then(() =>
          store.dispatch('application/forceUpdate', {
            application: database,
            data: { _integrationsLoadedOnce: true },
          })
        )
        .finally(() => inFlight.delete(database.id))
    )
  }
  await inFlight.get(database.id)
}

export default {
  name: 'DatabaseWorkflowActionWithService',
  components: { SampleDataViewer },
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
    // A type whose result only a real answer can describe, so the editor has
    // something to say about it whether or not a click has answered yet.
    capturesSampleData() {
      return this.workflowActionType.capturesSampleData
    },
    /**
     * What the last click remembered, from the saved service rather than the
     * buffered values: nothing in this editor can produce it. A stored error
     * describes no shape, so it counts as nothing captured.
     */
    /** Why the last click described nothing, when that is what happened. */
    capturedNothing() {
      return Boolean(this.defaultValues.service?.sample_data?._error)
    },
    sampleData() {
      const sample = this.defaultValues.service?.sample_data
      if (!sample) {
        return null
      }
      // A click that answered 404, timed out, or came back too big leaves the
      // reason instead of a shape. Shown in place of the note asking for a
      // click that has already happened.
      if (sample._error) {
        return sample._error
      }
      // What is stored is the whole dispatch result. The explorer's paths
      // start inside its `data`, so the viewer shows what they name.
      return sample.data ?? null
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
        ...this.workflowActionType.serviceFormProps,
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
  async created() {
    if (!this.workflowActionType.needsIntegration) {
      return
    }
    try {
      await fetchIntegrationsOnce(this.$store, this.database)
    } catch (error) {
      // Otherwise the dropdown reads as a database with no bot, and the only
      // thing offered is creating a second one.
      notifyIf(error, 'application')
    }
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
        // Marked rather than left alone, so the explorer offers this action's
        // `id` and nothing else. Without it the schema falls back to the last
        // save's, which describes the table it pointed at before.
        this.registerTableFields?.(tableId, FIELDS_UNAVAILABLE)
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
