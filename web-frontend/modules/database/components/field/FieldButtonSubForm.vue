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
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaInputField from '@baserow/modules/core/components/formula/FormulaInputField'
import ButtonFieldActionList from '@baserow/modules/database/components/field/ButtonFieldActionList'
import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import { reconcileWorkflowActions } from '@baserow/modules/database/utils/workflowActionReconciliation'
import { clone } from '@baserow/modules/core/utils/object'
import { buildFormulaFunctionNodes } from '@baserow/modules/core/formula'
import { getDataNodesFromDataProvider } from '@baserow/modules/core/utils/dataProviders'

export default {
  name: 'FieldButtonSubForm',
  components: { FormulaInputField, ButtonFieldActionList },
  mixins: [form, fieldSubForm],
  // The nested action forms (via FieldMappingsForm) need the workspace to
  // check field permissions.
  provide() {
    return {
      workspace: this.database.workspace,
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
    // list stays empty and every local action is new.
    if (this.defaultValues.id) {
      const { data } = await WorkflowActionService(this.$client).fetchAll(
        this.defaultValues.id
      )
      this.serverActions = data
      // A deep copy: editing localActions must never mutate serverActions,
      // or the reconciliation below would diff a list against itself.
      this.localActions = clone(data)
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
    updatedFormulaStr(newFormulaStr) {
      this.v$.values.url_formula.formula.$model = newFormulaStr
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

      for (const action of toCreate) {
        const { data } = await service.create(fieldId, action.type)
        createdIds.push(data.id)
        if (action.service && Object.keys(action.service).length > 0) {
          await service.update(data.id, { service: action.service })
        }
      }

      for (const { id, values } of toUpdate) {
        await service.update(id, values)
      }

      for (const id of toDelete) {
        await service.delete(id)
      }

      // `order` carries null where a created action's id was unknown; fill
      // them in from the creates, in the order they were made.
      const created = [...createdIds]
      const finalOrder = order.map((id) => (id === null ? created.shift() : id))

      if (finalOrder.length > 0) {
        await service.order(fieldId, finalOrder)
      }
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
