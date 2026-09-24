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
    <!--
      Keyed, because each action's form copies its values once when it is
      made. A list replaced from the server rebuilds them, or a card would keep
      showing, and saving, what was there before.
    -->
    <ButtonFieldActionList
      v-else
      :key="actionListRevision"
      ref="actionList"
      :value="localActions"
      :database="database"
      :table-fields="tableFields"
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
import FieldService from '@baserow/modules/database/services/field'
import {
  CLIENT_ID_KEY,
  countUndoSteps,
  rebaseWorkflowActions,
  reconcileWorkflowActions,
  workflowActionConfig,
  workflowActionKey,
} from '@baserow/modules/database/utils/workflowActionReconciliation'
import {
  rewriteActionFormulaIds,
  unresolvedActionIds,
} from '@baserow/modules/database/utils/workflowActionFormulas'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  FIELDS_UNAVAILABLE,
  TABLE_MISSING,
} from '@baserow/modules/database/utils/buttonField'
import { MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP } from '@baserow/modules/database/utils/action'

/**
 * An action without the answer a click left on its service, and without the
 * client id a saved action keeps for the card it is edited under.
 */
const withoutCapturedAnswers = (action) => {
  // Destructured rather than `_.omit`, which would copy the schema it keeps.
  const { [CLIENT_ID_KEY]: clientId, ...bare } = action
  return bare.service
    ? { ...bare, service: _.omit(bare.service, ['sample_data', 'schema']) }
    : bare
}

/**
 * Puts the client id an action was edited under back onto the action the
 * server handed back for it, so its card does not remount and lose its
 * scroll and open state. Only a client id: an id the action used to have
 * can come back from the trash and would then key two cards the same.
 */
const keepClientIds = (actions, clientIdByServerId) =>
  actions.map((action) =>
    clientIdByServerId.has(action.id)
      ? { ...action, [CLIENT_ID_KEY]: clientIdByServerId.get(action.id) }
      : action
  )

export default {
  name: 'FieldButtonSubForm',
  components: { ButtonFieldActionList },
  mixins: [form, fieldSubForm],
  provide() {
    return {
      workspace: this.database.workspace,
      // `InjectedFormulaInput` resolves what to render from this injection.
      formulaComponent: markRaw(DatabaseFormulaInput),
      // An action's arguments resolve the clicked row and what the actions
      // before them returned (ADR 006 section 4). Human readable values are
      // absent from the dispatch context, so `fields` is not offered.
      dataProvidersAllowed: ['row', 'previous_action'],
      // Lazy, so the explorer picks up the table's fields as they load.
      databaseFormulaContext: computed(() => this.applicationContext),
      registerTableFields: this.registerTableFields,
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
      // Bumped when the buffer is replaced from the server, to rebuild the
      // action forms.
      actionListRevision: 0,
      loadingActions: false,
      // Target table fields, by table id, reported by the action forms that
      // fetched them. An action that has never been saved carries no service
      // schema, so this is the only description of what it will return.
      tableFields: {},
      // Only the server can tell, since it depends on what is in the trash.
      // Refreshed after every save, as the field response predates the
      // actions it saved. Null when the last refresh failed or none ran.
      requiresReconfiguration: null,
      opensNewTab: null,
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
      Object.defineProperty(context, 'workflowActions', {
        enumerable: true,
        get: () => this.localActions,
      })
      Object.defineProperty(context, 'tableFields', {
        enumerable: true,
        get: () => this.tableFields,
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
    /** The action list is outside the form chain, so touch it here too. */
    touch(deep = false) {
      form.methods.touch.call(this, deep)
      this.$refs.actionList?.touch()
    },
    registerTableFields(tableId, fields) {
      // Two actions can point at the same table, and a fetch that failed for
      // one of them says nothing about the fields the other already has, or
      // about a table the other found missing.
      const known = this.tableFields[tableId]
      if (
        fields === FIELDS_UNAVAILABLE &&
        (Array.isArray(known) || known === TABLE_MISSING)
      ) {
        return
      }
      this.tableFields = { ...this.tableFields, [tableId]: fields }
    },
    /**
     * Rewrites the client ids in a payload's formulas to the real ones. A
     * client id left over means an action referenced one that had not been
     * created, so it is raised rather than sent.
     */
    resolveActionIds(payload, idMap) {
      const resolved = rewriteActionFormulaIds(payload, idMap)
      const unresolved = unresolvedActionIds(resolved)
      if (unresolved.length > 0) {
        throw this.unresolvedReferenceError(unresolved)
      }
      return resolved
    },
    /**
     * `notifyIf` presents an error only when it carries a handler, and rethrows
     * anything else. A rethrow here would escape the caller before it can flag
     * the failure, and the editor would then close and discard the very edits
     * the user has to fix. Carrying a handler keeps it a normal failed save.
     */
    unresolvedReferenceError(unresolved) {
      const error = new Error(
        `Unresolved workflow action reference: ${unresolved.join(', ')}`
      )
      error.handler = {
        notifyIf: () => {
          this.$store.dispatch('toast/error', {
            title: this.$t('fieldButtonSubForm.unresolvedReferenceTitle'),
            message: this.$t('fieldButtonSubForm.unresolvedReferenceMessage'),
          })
        },
      }
      return error
    },
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
      // The flag is keyed by what the card was edited under, so it would
      // outlive the cancel and keep hiding that action's own error.
      this.$refs.actionList?.revealErrors()
      // The action forms copy their values once, so a card would otherwise
      // keep showing, and later send, the edit that was cancelled.
      this.actionListRevision += 1
    },
    /**
     * Fetches the field's actions and resets both the server list and the
     * editable copy. Also called after a save, so a second save reconciles
     * against real ids rather than re-creating what the first one made.
     */
    async fetchWorkflowActions(
      fieldId,
      { keepEdits = false, clientIds = new Map() } = {}
    ) {
      const { data } = await WorkflowActionService(this.$client).fetchAll(
        fieldId
      )
      this.serverActions = data
      if (!keepEdits) {
        // Deep copy, or the reconciliation would diff a list against itself.
        // Keyed before it is assigned: a render in between would remount the
        // created action's card under its id.
        this.localActions = keepClientIds(clone(data), clientIds)
      }
    },
    /**
     * Re-reads the field's actions. They change while the editor is closed: a
     * click makes an external action remember the answer it got, and an undo
     * or a collaborator changes the list itself. This sub-form is not
     * remounted when the field is opened again, so without this the editor
     * shows the old list, and saving it would put back what was undone.
     *
     * An edit made and then clicked away from survives: nothing listens for
     * the context being hidden, so the buffered list is still here on the next
     * open, and replacing it would drop that edit without a word. So a buffer
     * without edits takes the server's list, and one with edits keeps them on
     * top of it. Skipped while the first read is still in flight, since
     * `mounted` and the context's own `shown` both land on the first open.
     */
    async onShow() {
      // The list is not remounted between opens, so reopening the editor is
      // the retry for an integrations fetch that failed. Reports its own
      // failure, so nothing here waits on it.
      this.$refs.actionList?.fetchIntegrations()
      if (
        !this.defaultValues.id ||
        this.defaultValues.type !== 'button' ||
        this.loadingActions
      ) {
        return
      }
      try {
        const { data } = await WorkflowActionService(this.$client).fetchAll(
          this.defaultValues.id
        )
        const localActions = this.hasUnsavedEdits()
          ? rebaseWorkflowActions(this.serverActions, data, this.localActions)
          : clone(data)
        this.serverActions = data
        // Compared without what a click captured, which the forms read live,
        // so a click alone does not collapse the card being looked at.
        if (
          !_.isEqual(
            localActions.map(withoutCapturedAnswers),
            this.localActions.map(withoutCapturedAnswers)
          )
        ) {
          this.localActions = localActions
          this.actionListRevision += 1
        }
        this.adoptCapturedAnswers(data)
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
    /**
     * Whether the buffered list differs from the one the server last reported.
     * An action added without a type yet counts, although no save would send it.
     */
    hasUnsavedEdits() {
      if (this.localActions.length !== this.serverActions.length) {
        return true
      }
      const { toCreate, toUpdate, toDelete, order } = reconcileWorkflowActions(
        this.serverActions,
        this.localActions
      )
      return (
        toCreate.length > 0 ||
        toUpdate.length > 0 ||
        toDelete.length > 0 ||
        !_.isEqual(
          order,
          this.serverActions.map((action) => action.id)
        )
      )
    },
    /**
     * Copies what a click remembered onto the buffered actions, matched by id.
     * The editor cannot change either of these, so nothing anybody typed is
     * overwritten.
     */
    adoptCapturedAnswers(serverActions) {
      const captured = new Map(
        serverActions
          .filter((action) => action.service)
          .map((action) => [
            action.id,
            {
              sample_data: action.service.sample_data,
              schema: action.service.schema,
            },
          ])
      )
      this.localActions = this.localActions.map((action) => {
        const answer = captured.get(action.id)
        return answer && action.service
          ? { ...action, service: { ...action.service, ...answer } }
          : action
      })
    },
    /**
     * Puts the ids the server just handed out onto the buffered actions they
     * belong to, so a save that stopped half way can be retried without
     * creating a second copy of everything the first attempt made.
     */
    adoptAssignedIds(assignedIds) {
      if (assignedIds.size === 0) {
        return
      }
      const idMap = Object.fromEntries(assignedIds)
      this.localActions = this.localActions.map((action) => {
        const created = assignedIds.get(workflowActionKey(action))
        // The client id stays on the action, so the card the user is fixing
        // keeps its place and the flag holding its error back.
        const adopted =
          created === undefined ? action : { ...action, id: created }
        // References to the actions that did get made have to follow them too.
        // Without this a retry sees a client id whose action is no longer in
        // `toCreate`, so nothing maps it and the save can never succeed.
        return rewriteActionFormulaIds(adopted, idMap)
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
     * An action and its config in one payload, so a create cannot half succeed
     * and leave a blank action on the server. The service is sent untyped: the
     * editor names service types differently from the API, and the action type
     * already settles which one this is.
     */
    createPayload(action) {
      const config = workflowActionConfig(action)
      if (config.service && Object.keys(config.service).length === 0) {
        delete config.service
      }
      return { type: action.type, ...config }
    },
    /**
     * Diffs the buffered list against the server and issues the calls to
     * match: creates, updates, deletes, then order. Called by the field form
     * once the field is saved, since a new field has no id until then.
     *
     * `undoRedoActionGroupId` is the group the field save was sent under, so
     * one undo takes back the field and its actions together. A save with more
     * steps than a group can undo at once is sent without it.
     */
    async afterFieldSaved(fieldId, { undoRedoActionGroupId = null } = {}) {
      const plan = reconcileWorkflowActions(
        this.serverActions,
        this.localActions
      )
      const { toCreate, toUpdate, toDelete, order } = plan
      // One undo takes back only the newest steps of a group, and the field
      // save is the oldest. A save that would not fit is sent ungrouped, so
      // each step undoes on its own rather than one undo leaving it half done.
      const groupId =
        1 + countUndoSteps(plan) <= MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP
          ? undoRedoActionGroupId
          : null
      const service = WorkflowActionService(this.$client)
      const createdIds = []
      const assignedIds = new Map()
      // The client id of each action the server handed a new id, by that id.
      // A create and a type change both do.
      const clientIdByServerId = new Map()
      const rememberClientId = (action, serverId) => {
        if (action?.[CLIENT_ID_KEY] != null) {
          clientIdByServerId.set(serverId, action[CLIENT_ID_KEY])
        }
      }
      let failed = false
      // Captured before the `finally` below re-fetches and replaces the list.
      const serverById = new Map(this.serverActions.map((a) => [a.id, a]))

      // An unsaved action is referenced by its client id until the server
      // gives it a real one. References only ever point backwards, so creating
      // in list order means everything an action names already has its id.
      const idMap = {}

      try {
        for (const action of toCreate) {
          const { data } = await service.create(
            fieldId,
            this.resolveActionIds(this.createPayload(action), idMap),
            groupId
          )
          createdIds.push(data.id)
          rememberClientId(action, data.id)
          // Both ways of naming it are mapped: an unsaved action is referenced
          // by its client id, while one the server has forgotten, deleted by a
          // collaborator say, is referenced by the id it used to have. Neither
          // is left out, or the actions after it would keep naming something
          // that no longer exists and every click would fail on it.
          for (const key of [action[CLIENT_ID_KEY], action.id]) {
            if (key != null) {
              assignedIds.set(key, data.id)
              idMap[key] = data.id
            }
          }
        }

        for (const { id, values } of toUpdate) {
          // A type change builds a new service, so the config follows once the
          // action is of the new type. Sending it along would type the service
          // from the server's copy, which is still the old type.
          const defersConfig = values.type !== undefined && 'service' in values
          const payload = this.resolveActionIds(
            defersConfig
              ? _.omit(values, 'service')
              : this.withTypedService(values, serverById.get(id)),
            idMap
          )
          // Skip rather than send an empty PATCH.
          if (Object.keys(payload).length === 0) {
            continue
          }
          const { data } = await service.update(id, payload, groupId)
          if (data?.id != null && data.id !== id) {
            rememberClientId(
              this.localActions.find((action) => action.id === id),
              data.id
            )
          }
          if (defersConfig) {
            const config = this.resolveActionIds(
              this.configPayload(values, data),
              idMap
            )
            if (Object.keys(config).length > 0) {
              await service.update(data?.id ?? id, config, groupId)
            }
          }
        }

        for (const id of toDelete) {
          await service.delete(id, groupId)
        }

        // `order` holds null for creates; fill them in as they were made.
        const created = [...createdIds]
        const finalOrder = order.map((id) =>
          id === null ? created.shift() : id
        )

        // Without an order call the server keeps what was there, less what
        // was deleted, and appends each create. Sending that same order again
        // would only add an undo step, and a group undoes a limited number.
        const deleted = new Set(toDelete)
        const orderWithoutCall = [
          ...this.serverActions
            .map((action) => action.id)
            .filter((id) => !deleted.has(id)),
          ...createdIds,
        ]

        if (finalOrder.length > 0 && !_.isEqual(finalOrder, orderWithoutCall)) {
          await service.order(fieldId, finalOrder, groupId)
        }
      } catch (error) {
        failed = true
        throw error
      } finally {
        // A failure leaves the edits in the buffer to be retried, but carrying
        // the ids of whatever did get made. The server list is refreshed
        // either way, so the retry diffs against what is really there.
        if (failed) {
          this.adoptAssignedIds(assignedIds)
        }
        try {
          // The fetched list has only ids. Keyed by those, a created action's
          // card would remount and the editor would scroll to the top while
          // it is still on screen.
          await this.fetchWorkflowActions(fieldId, {
            keepEdits: failed,
            clientIds: clientIdByServerId,
          })
        } catch (refreshError) {
          notifyIf(refreshError, 'field')
        }
        await this.refreshFieldFlags(fieldId)
      }
    },
    /**
     * Asks the server whether the saved actions leave the button needing
     * reconfiguration or opening a new tab. On failure the flags are unknown:
     * the next broadcast or reload corrects them, and a toast here would bury
     * the save's own result.
     */
    async refreshFieldFlags(fieldId) {
      this.requiresReconfiguration = null
      this.opensNewTab = null
      try {
        const { data } = await FieldService(this.$client).get(fieldId)
        this.requiresReconfiguration = data?.requires_reconfiguration === true
        this.opensNewTab = data?.opens_new_tab === true
      } catch {
        // Left unknown, see above.
      }
    },
    /**
     * The field response carries `has_workflow_actions`,
     * `requires_reconfiguration` and `opens_new_tab` computed before these
     * calls, so the store needs the flags as they ended up. The reconfigure
     * and new tab flags are left out when the refresh failed, so the store
     * keeps what it has.
     */
    fieldValuesAfterSave() {
      const values = { has_workflow_actions: this.serverActions.length > 0 }
      if (this.requiresReconfiguration !== null) {
        values.requires_reconfiguration = this.requiresReconfiguration
      }
      if (this.opensNewTab !== null) {
        values.opens_new_tab = this.opensNewTab
      }
      return values
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
