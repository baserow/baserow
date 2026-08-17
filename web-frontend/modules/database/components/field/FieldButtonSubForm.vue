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
    <!-- An edit made before the saved actions arrive would be lost to them. -->
    <div v-if="loadingActions" class="loading-spinner margin-top-2"></div>
    <ButtonFieldActionList
      v-else
      :value="localActions"
      :database="database"
      @input="localActions = $event"
    />
  </div>
</template>

<script>
import _ from 'lodash'
import { computed, markRaw } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import ButtonFieldActionList from '@baserow/modules/database/components/field/ButtonFieldActionList'
import DatabaseFormulaInput from '@baserow/modules/database/components/field/DatabaseFormulaInput'
import WorkflowActionService from '@baserow/modules/database/services/workflowAction'
import {
  CLIENT_ID_KEY,
  reconcileWorkflowActions,
  workflowActionConfig,
} from '@baserow/modules/database/utils/workflowActionReconciliation'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'FieldButtonSubForm',
  components: { ButtonFieldActionList },
  mixins: [form, fieldSubForm],
  provide() {
    return {
      workspace: this.database.workspace,
      // `InjectedFormulaInput` resolves what to render from this injection.
      formulaComponent: markRaw(DatabaseFormulaInput),
      // An action's arguments can only resolve the clicked row; the dispatch
      // context carries no human readable values (ADR 006 section 4).
      dataProvidersAllowed: ['row'],
      // Lazy, so the explorer picks up the table's fields as they load.
      databaseFormulaContext: computed(() => this.applicationContext),
    }
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['label'],
      values: {
        label: '',
      },
      // The last server response and the editable copy, kept apart so
      // cancelling discards the edits without ever calling the API.
      serverActions: [],
      localActions: [],
      loadingActions: false,
    }
  },
  computed: {
    applicationContext() {
      const context = {}
      Object.defineProperty(context, 'fields', {
        enumerable: true,
        // A write only field is left out: the dispatch refuses to read one, so
        // offering it would only build a formula that fails on click.
        get: () =>
          this.allFieldsInTable.filter(
            (f) =>
              f.id !== this.defaultValues.id &&
              !this.$registry.get('field', f.type).isWriteOnlyField(f)
          ),
      })
      return context
    },
  },
  async mounted() {
    // FieldForm swaps this sub-form in while the user browses the type
    // dropdown, when `defaultValues` is still a saved field of another type.
    if (this.defaultValues.id && this.defaultValues.type === 'button') {
      this.loadingActions = true
      try {
        await this.fetchWorkflowActions(this.defaultValues.id)
      } catch (error) {
        notifyIf(error, 'field')
      } finally {
        this.loadingActions = false
      }
    }
  },
  methods: {
    /**
     * Only the field's own values. The nested service forms register up this
     * chain, and their values go to the workflow action endpoints instead.
     */
    getFormValues() {
      return { ...this.values }
    },
    /**
     * The sub-form survives across opens, and `reset()` only clears `values`,
     * so the buffered list has to be rebuilt here or a discarded action would
     * still be listed on the next open.
     */
    async reset(deep = false) {
      await form.methods.reset.call(this, deep)
      this.localActions = clone(this.serverActions)
    },
    /**
     * Fetches the field's actions and resets both the server list and the
     * editable copy. Also called after a save, so a second save reconciles
     * against real ids rather than re-creating what the first one made.
     */
    async fetchWorkflowActions(fieldId, { keepEdits = false } = {}) {
      const { data } = await WorkflowActionService(this.$client).fetchAll(
        fieldId
      )
      this.serverActions = data
      if (!keepEdits) {
        // Deep copy, or the reconciliation would diff a list against itself.
        this.localActions = clone(data)
      }
    },
    /**
     * Puts the ids the server just handed out onto the buffered actions they
     * belong to, so a save that stopped half way can be retried without
     * creating a second copy of everything the first attempt made.
     */
    adoptAssignedIds(assignedIds, replacedIds) {
      if (assignedIds.size === 0 && replacedIds.size === 0) {
        return
      }
      this.localActions = this.localActions.map((action) => {
        const created = assignedIds.get(action[CLIENT_ID_KEY])
        if (created !== undefined) {
          return { ...action, id: created }
        }
        const replaced = replacedIds.get(action.id)
        return replaced === undefined ? action : { ...action, id: replaced }
      })
    },
    /**
     * Adds the `type` the API needs to a payload's `service`, taken from the
     * action as the server knows it. A buffered service carries no type of its
     * own, and the polymorphic serializer 500s on one it cannot type. An empty
     * service says nothing anyway, so it is dropped rather than sent untyped.
     */
    withTypedService(payload, serverSide) {
      if (!payload.service) {
        return payload
      }
      if (Object.keys(payload.service).length === 0) {
        return _.omit(payload, 'service')
      }
      return {
        ...payload,
        service: { type: serverSide?.service?.type, ...payload.service },
      }
    },
    /**
     * The follow-up payload that applies a buffered config to an action the
     * server has just created. `type` is dropped so the follow-up cannot
     * trigger a second recreate.
     */
    configPayload(action, created) {
      return this.withTypedService(workflowActionConfig(action), created)
    },
    /**
     * Diffs the buffered list against the server and issues the calls to
     * match: creates, updates, deletes, then order. Called by the field form
     * once the field is saved, since a new field has no id until then.
     */
    async afterFieldSaved(fieldId) {
      const { toCreate, toUpdate, toDelete, order } = reconcileWorkflowActions(
        this.serverActions,
        this.localActions
      )
      const service = WorkflowActionService(this.$client)
      const createdIds = []
      const replacedIds = new Map()
      const assignedIds = new Map()
      let failed = false
      // Captured before the `finally` below re-fetches and replaces the list.
      const serverById = new Map(this.serverActions.map((a) => [a.id, a]))

      try {
        for (const action of toCreate) {
          const { data } = await service.create(fieldId, action.type)
          createdIds.push(data.id)
          assignedIds.set(action[CLIENT_ID_KEY], data.id)
          const values = this.configPayload(action, data)
          if (Object.keys(values).length > 0) {
            await service.update(data.id, values)
          }
        }

        for (const { id, values } of toUpdate) {
          // A type change recreates the action server side, so it goes on its
          // own and the config follows against the new id. Otherwise the
          // service may still be untyped, so type it from the server's copy.
          const defersConfig = values.type !== undefined && 'service' in values
          const payload = defersConfig
            ? _.omit(values, 'service')
            : this.withTypedService(values, serverById.get(id))
          // Skip rather than send an empty PATCH.
          if (Object.keys(payload).length === 0) {
            continue
          }
          const { data } = await service.update(id, payload)
          // The recreate hands back a new id; the order below holds the old.
          if (data?.id != null && data.id !== id) {
            replacedIds.set(id, data.id)
          }
          if (defersConfig) {
            const config = this.configPayload(values, data)
            if (Object.keys(config).length > 0) {
              await service.update(data?.id ?? id, config)
            }
          }
        }

        for (const id of toDelete) {
          await service.delete(id)
        }

        // `order` holds null for creates; fill them in as they were made.
        const created = [...createdIds]
        const finalOrder = order.map((id) =>
          id === null ? created.shift() : (replacedIds.get(id) ?? id)
        )

        if (finalOrder.length > 0) {
          await service.order(fieldId, finalOrder)
        }
      } catch (error) {
        failed = true
        throw error
      } finally {
        // A failure leaves the edits in the buffer to be retried, but carrying
        // the ids of whatever did get made. The server list is refreshed
        // either way, so the retry diffs against what is really there.
        if (failed) {
          this.adoptAssignedIds(assignedIds, replacedIds)
        }
        try {
          await this.fetchWorkflowActions(fieldId, { keepEdits: failed })
        } catch (refreshError) {
          notifyIf(refreshError, 'field')
        }
      }
    },
    /**
     * The field response carries a `has_workflow_actions` computed before the
     * actions were saved, so the store needs the flag as it ended up.
     */
    fieldValuesAfterSave() {
      return { has_workflow_actions: this.serverActions.length > 0 }
    },
  },
  validations() {
    return {
      values: {
        label: { required },
      },
    }
  },
}
</script>
