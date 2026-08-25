<template>
  <div class="button-field-action-list">
    <div class="button-field-action-list__divider"></div>
    <div class="button-field-action-list__heading">
      <div class="button-field-action-list__title">
        {{ $t('buttonFieldActionList.actions') }}
      </div>
      <ButtonText type="secondary" icon="iconoir-plus" @click="addAction()">
        {{ $t('buttonFieldActionList.addAction') }}
      </ButtonText>
    </div>

    <Alert v-if="misconfigured" type="warning" class="margin-bottom-2">
      {{ $t('buttonFieldActionList.misconfigured') }}
    </Alert>

    <!--
      The sortable directive reads the new order off every element child of
      this wrapper, so anything that is not an action stays outside it.
    -->
    <div class="button-field-action-list__items">
      <div
        v-for="(action, index) in value"
        :key="actionKey(action)"
        v-sortable="{
          id: actionKey(action),
          handle: '[data-sortable-handle]',
          update: onSortableUpdate,
        }"
        class="button-field-action-list__item margin-bottom-2"
      >
        <div
          class="button-field-action-list__header"
          @click="toggleAction(action)"
        >
          <!--
            The handle, the type dropdown and the delete button all sit in the
            header, so each stops the click that would otherwise reach the
            header and toggle the card.
          -->
          <div
            class="button-field-action-list__handle"
            data-sortable-handle
            @click.stop
          ></div>
          <div class="button-field-action-list__type" @click.stop>
            <Dropdown
              :value="action.type ?? null"
              :placeholder="$t('buttonFieldActionList.chooseAction')"
              :search-text="$t('buttonFieldActionList.searchActions')"
              :fixed-items="true"
              @input="onActionTypeChanged(index, $event)"
            >
              <DropdownItem
                v-for="actionType in availableActionTypes"
                :key="actionType.getType()"
                :icon="actionType.icon"
                :name="actionType.label"
                :value="actionType.getType()"
              ></DropdownItem>
            </Dropdown>
          </div>
          <div @click.stop>
            <ButtonIcon
              icon="iconoir-bin"
              @click="removeAction(index)"
            ></ButtonIcon>
          </div>
          <i
            v-if="action.type"
            class="button-field-action-list__toggle"
            :class="
              isExpanded(action)
                ? 'iconoir-nav-arrow-down'
                : 'iconoir-nav-arrow-right'
            "
            data-action-toggle
          />
        </div>
        <!--
          Outside the collapsible part on purpose: a misconfigured action has
          to be findable without opening every card in the list.
        -->
        <div
          v-if="errorFor(action)"
          class="button-field-action-list__error"
          data-action-error
        >
          {{ errorFor(action) }}
        </div>
        <!--
          Hidden rather than unmounted. The per-action form registers into this
          form's chain and emits its defaults on mount, so tearing it down on
          collapse would quietly change what a save sends.
        -->
        <template v-if="action.type">
          <div
            v-show="isExpanded(action)"
            class="button-field-action-list__separator"
          ></div>
          <div
            v-show="isExpanded(action)"
            class="button-field-action-list__form"
          >
            <ButtonFieldActionForm
              :action="action"
              :database="database"
              @values-changed="onActionValuesChanged(index, $event)"
            />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'
import { uuid } from '@baserow/modules/core/utils/string'
import ButtonFieldActionForm from '@baserow/modules/database/components/field/ButtonFieldActionForm'
import {
  CLIENT_ID_KEY,
  workflowActionKey,
} from '@baserow/modules/database/utils/workflowActionReconciliation'

/**
 * Controlled editor for a button field's ordered action list. Owns no state
 * beyond `value`: every mutation emits a new array and makes no API calls, so
 * the sub-form can discard changes by not saving.
 */
export default {
  name: 'ButtonFieldActionList',
  components: { ButtonFieldActionForm },
  inject: {
    workspace: { from: 'workspace', default: null },
  },
  props: {
    value: {
      type: Array,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  emits: ['input'],
  data() {
    return {
      // Which cards are open, keyed the same way the list keys its rows. An
      // action added here opens itself; everything the editor loaded starts
      // closed, the way the builder's event list does.
      expandedActions: {},
    }
  },
  computed: {
    availableActionTypes() {
      return this.$registry.getOrderedList('databaseWorkflowActionType')
    },
    misconfigured() {
      return Object.values(this.errorsByAction).some((error) => error)
    },
    /**
     * A warning rather than a validation gate: a half configured action is a
     * normal state while editing, and the field saves either way.
     *
     * Built once per list rather than per action: checking a reference walks
     * the whole config, which on a wide table is thousands of properties, and
     * the template asks for each action's error more than once.
     */
    errorsByAction() {
      const context = {
        workspace: this.workspace,
        workflowActions: this.value,
      }
      return Object.fromEntries(
        this.value.map((action) => [
          workflowActionKey(action),
          action.type
            ? this.$registry
                .get('databaseWorkflowActionType', action.type)
                .getErrorMessage(action, context)
            : null,
        ])
      )
    },
  },
  methods: {
    actionKey(action) {
      return workflowActionKey(action)
    },
    errorFor(action) {
      return this.errorsByAction[workflowActionKey(action)] ?? null
    },
    /**
     * An action with no type yet has nothing to show, so it stays shut
     * whatever the state says.
     */
    isExpanded(action) {
      return (
        Boolean(action.type) &&
        this.expandedActions[workflowActionKey(action)] === true
      )
    },
    /**
     * One card at a time. Several open at once makes the editor taller than
     * the screen, and the data explorer then opens over the list instead of
     * under the input it belongs to.
     */
    toggleAction(action) {
      const key = workflowActionKey(action)
      this.expandedActions = this.expandedActions[key] ? {} : { [key]: true }
    },
    /**
     * No type until the user picks one, and no `id` until the field is saved.
     */
    addAction(type = null) {
      const action = this.newAction(type)
      // Open straight away, and only this one: building a chain otherwise
      // leaves every card of it open and the editor grows past the screen.
      this.expandedActions = { [workflowActionKey(action)]: true }
      this.$emit('input', [...this.value, action])
    },
    newAction(type) {
      if (type === null) {
        return { [CLIENT_ID_KEY]: uuid(), type: null }
      }
      return {
        [CLIENT_ID_KEY]: uuid(),
        type,
        ...this.$registry
          .get('databaseWorkflowActionType', type)
          .getNewActionValues(),
      }
    },
    /**
     * The old config is dropped, since it means nothing to the new type. The
     * `id` is kept so the change reconciles as an update and keeps its place,
     * and the client id so the row stays the same row.
     */
    onActionTypeChanged(index, type) {
      const action = this.value[index]
      if (action.type === type) {
        return
      }
      const replacement = this.newAction(type)
      if (action.id != null) {
        replacement.id = action.id
      }
      if (action[CLIENT_ID_KEY] != null) {
        replacement[CLIENT_ID_KEY] = action[CLIENT_ID_KEY]
      }
      this.$emit(
        'input',
        this.value.map((a, i) => (i === index ? replacement : a))
      )
    },
    removeAction(index) {
      this.$emit(
        'input',
        this.value.filter((_action, i) => i !== index)
      )
    },
    orderActions(newList) {
      this.$emit('input', newList)
    },
    /**
     * The per-action form emits `values-changed` once on mount even when
     * nothing changed, so only emit `input` when a key genuinely differs.
     */
    onActionValuesChanged(index, values) {
      const action = this.value[index]
      if (_.isEqual(values, _.pick(action, Object.keys(values)))) {
        return
      }
      const newList = this.value.map((a, i) =>
        i === index ? { ...a, ...values } : a
      )
      this.$emit('input', newList)
    },
    onSortableUpdate(newOrder) {
      const bySortId = new Map(
        this.value.map((action) => [this.actionKey(action), action])
      )
      // An id with no action behind it would render as undefined and crash.
      const reordered = newOrder
        .map((id) => bySortId.get(id))
        .filter((action) => action !== undefined)
      if (reordered.length !== this.value.length) {
        return
      }
      this.orderActions(reordered)
    },
  },
}
</script>
