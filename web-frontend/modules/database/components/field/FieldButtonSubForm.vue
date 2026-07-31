<template>
  <div class="context__form-container">
    <FormGroup
      small-label
      required
      :label="$t('fieldButtonSubForm.label')"
      :error="fieldHasErrors('label')"
    >
      <FormInput
        v-model="v$.values.label.$model"
        :placeholder="$t('fieldButtonSubForm.labelPlaceholder')"
      />
      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>
    <FormGroup
      small-label
      required
      :label="$t('fieldButtonSubForm.url')"
      :error="v$.values.url_formula?.formula.$error || urlInvalid"
    >
      <FormulaInputField
        :value="formulaStr"
        :mode="localMode"
        :nodes-hierarchy="nodesHierarchy"
        :placeholder="$t('fieldButtonSubForm.urlPlaceholder')"
        :validation-context="{ dataProviderRegistry: dataProviders }"
        @input="updatedFormulaStr"
        @update:mode="updateMode"
        @update:invalid="urlInvalid = $event"
      />
      <template #error>
        {{
          urlInvalid
            ? $t('fieldButtonSubForm.invalidUrl')
            : $t('error.requiredField')
        }}
      </template>
    </FormGroup>
    <ButtonFieldActionList
      :value="localActions"
      :database="database"
      @input="localActions = $event"
    />
  </div>
</template>

<script>
import { computed, markRaw } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import ButtonFieldActionList from '@baserow/modules/database/components/field/ButtonFieldActionList'
import DatabaseFormulaInput from '@baserow/modules/database/components/field/DatabaseFormulaInput'
import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import { reconcileWorkflowActions } from '@baserow/modules/database/utils/workflowActionReconciliation'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'

export default {
  name: 'FieldButtonSubForm',
  components: { FormulaInputField, ButtonFieldActionList },
  mixins: [form, fieldSubForm],
  provide() {
    return {
      // The nested action forms (via FieldMappingsForm) need the workspace to
      // check field permissions.
      workspace: this.database.workspace,
      // A field mapping renders its formula input through the shared
      // `InjectedFormulaInput`, which resolves the component to render from
      // this injection. Without it the injection is undefined and the input
      // renders as an empty area. The builder and automation editors provide
      // their own component the same way.
      formulaComponent: markRaw(DatabaseFormulaInput),
      // Only the clicked row resolves in a button action's arguments: a
      // `DatabaseDispatchContext` carries no human readable values, so
      // `get('fields.…')` would resolve to nothing (ADR 006 section 4).
      dataProvidersAllowed: ['row'],
      // Lazily read, so the explorer picks up the table's fields as they load.
      databaseFormulaContext: computed(() => this.applicationContext),
    }
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['label', 'url_formula'],
      values: {
        label: '',
        url_formula: { formula: '', mode: 'simple' },
      },
      localMode: 'simple',
      urlInvalid: false,
      // The list as last fetched from the server, and the editable copy the
      // user works on. Kept apart so cancelling the field form discards
      // `localActions` without ever having called the API.
      serverActions: [],
      localActions: [],
    }
  },
  computed: {
    formulaStr() {
      return this.values.url_formula.formula
    },
    applicationContext() {
      const context = {}
      Object.defineProperty(context, 'fields', {
        enumerable: true,
        get: () =>
          this.allFieldsInTable.filter((f) => f.id !== this.defaultValues.id),
      })
      return context
    },
    dataProviders() {
      return [this.$registry.get('databaseDataProvider', 'fields')]
    },
    nodesHierarchy() {
      const hierarchy = []
      const filteredDataNodes = getDataNodesFromDataProvider(
        this.dataProviders,
        this.applicationContext
      )
      if (filteredDataNodes.length > 0) {
        hierarchy.push({
          name: this.$t('runtimeFormulaTypes.formulaTypeData'),
          type: 'data',
          icon: 'iconoir-database',
          nodes: filteredDataNodes,
        })
      }
      hierarchy.push(...buildFormulaFunctionNodes(this))
      return hierarchy
    },
  },
  watch: {
    'values.url_formula.mode': {
      handler(newMode) {
        if (newMode && newMode !== this.localMode) {
          this.localMode = newMode
        }
      },
      immediate: true,
    },
  },
  async mounted() {
    // A new field has no id yet, so there is nothing to fetch: the server
    // list stays empty and every local action is new. Also guard on the
    // field actually being a button field: FieldForm swaps this sub-form in
    // live as the user browses the type dropdown, so `defaultValues` can
    // still be the persisted field of a different type (with a real id)
    // while this component is only being previewed.
    if (this.defaultValues.id && this.defaultValues.type === 'button') {
      try {
        await this.fetchWorkflowActions(this.defaultValues.id)
      } catch (error) {
        // Degrade to an empty list instead of an unhandled rejection; the
        // user can still add actions from scratch.
        notifyIf(error, 'field')
      }
    }
  },
  methods: {
    /**
     * The formula input only emits parseable formulas, so block submission
     * while the editor content is invalid instead of saving a stale formula.
     */
    isFormValid(deep = false) {
      return !this.urlInvalid && form.methods.isFormValid.call(this, deep)
    },
    /**
     * Only the field's own values, never the child forms'. The action editor's
     * service forms register up this chain (`ButtonFieldActionList` is not a
     * form, so it is transparent), and the default implementation would fold
     * their `service`, `table_id`, `field_mappings` and so on into the field
     * create/update payload. Their values are persisted by
     * `saveWorkflowActions` instead, against the workflow action endpoints.
     */
    getFormValues() {
      return { ...this.values }
    },
    updatedFormulaStr(newFormulaStr) {
      this.v$.values.url_formula.formula.$model = newFormulaStr
    },
    /**
     * `UpdateFieldContext` keeps one instance of this sub-form per field
     * alive across opens (Context.vue renders on `openedOnce`), so nothing
     * remounts when the editor is reopened. Cancelling only calls `reset()`,
     * which the form mixin applies to `values` alone, leaving the buffered
     * action list untouched. Rebuild it from the last server response here,
     * or a discarded action stays listed on the next open and gets created
     * for real if the user then saves.
     */
    async reset(deep = false) {
      await form.methods.reset.call(this, deep)
      this.localActions = clone(this.serverActions)
    },
    /**
     * Fetches the field's actions from the server and resets both
     * `serverActions` and the editable `localActions` copy from the
     * response. Used both on mount and to re-sync after a save, so a
     * second save in the same mounted instance reconciles against real
     * ids instead of re-creating actions the first save already made.
     */
    async fetchWorkflowActions(fieldId) {
      const { data } = await WorkflowActionService(this.$client).fetchAll(
        fieldId
      )
      this.serverActions = data
      // A deep copy: editing localActions must never mutate serverActions,
      // or the reconciliation below would diff a list against itself.
      this.localActions = clone(data)
    },
    /**
     * Reconciles the buffered action list against the server and issues the
     * calls to match: creates, updates, deletes, then order. Called by the
     * field form once the field itself has been saved, because a new field
     * has no id until then.
     */
    async saveWorkflowActions(fieldId) {
      const { toCreate, toUpdate, toDelete, order } = reconcileWorkflowActions(
        this.serverActions,
        this.localActions
      )
      const service = WorkflowActionService(this.$client)
      const createdIds = []

      try {
        for (const action of toCreate) {
          const { data } = await service.create(fieldId, action.type)
          createdIds.push(data.id)
          if (action.service && Object.keys(action.service).length > 0) {
            // A buffered service carries no `type` until the server has made
            // one, and the API's polymorphic service serializer refuses a
            // payload it cannot type. Take it from the service the create
            // just returned, letting the buffer win if it ever has its own.
            await service.update(data.id, {
              service: { type: data.service?.type, ...action.service },
            })
          }
        }

        for (const { id, values } of toUpdate) {
          await service.update(id, values)
        }

        for (const id of toDelete) {
          await service.delete(id)
        }

        // `order` carries null where a created action's id was unknown;
        // fill them in from the creates, in the order they were made.
        const created = [...createdIds]
        const finalOrder = order.map((id) =>
          id === null ? created.shift() : id
        )

        if (finalOrder.length > 0) {
          await service.order(fieldId, finalOrder)
        }
      } finally {
        // Re-sync from the server whether the above succeeded or partially
        // failed. On success this captures the real ids the server
        // assigned, so a later save in the same mounted instance never
        // treats an already-created action as new again. On a partial
        // failure it shows the user what actually persisted instead of the
        // stale local buffer. A failure here must not mask the original
        // error, which is left to keep propagating to the caller.
        try {
          await this.fetchWorkflowActions(fieldId)
        } catch (refreshError) {
          notifyIf(refreshError, 'field')
        }
      }
    },
    /**
     * Whether the field has actions server side, as of the last sync. Read by
     * the field create/update contexts to patch the store, because the
     * `has_workflow_actions` the field response carried was computed before
     * `saveWorkflowActions` ran.
     */
    hasWorkflowActions() {
      return this.serverActions.length > 0
    },
    updateMode(newMode) {
      this.localMode = newMode
      this.values.url_formula = { ...this.values.url_formula, mode: newMode }
    },
  },
  validations() {
    return {
      values: {
        label: { required },
        url_formula: { formula: { required } },
      },
    }
  },
}
</script>
