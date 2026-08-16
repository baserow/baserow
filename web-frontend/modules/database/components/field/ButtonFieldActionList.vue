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
        <div class="button-field-action-list__header">
          <div
            class="button-field-action-list__handle"
            data-sortable-handle
          ></div>
          <Dropdown
            class="button-field-action-list__type"
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
          <ButtonIcon
            icon="iconoir-bin"
            @click="removeAction(index)"
          ></ButtonIcon>
        </div>
        <template v-if="action.type">
          <div class="button-field-action-list__separator"></div>
          <div class="button-field-action-list__form">
            <!--
              Keyed by type because `create_row` and `update_row` share a form
              component, so otherwise Vue reuses the instance on a type swap
              and keeps the old type's values.
            -->
            <component
              :is="actionTypeOf(action).form"
              :key="action.type"
              v-bind="
                actionTypeOf(action).getFormProps({
                  workflowAction: action,
                  database,
                })
              "
              :default-values="action"
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
import { CLIENT_ID_KEY } from '@baserow/modules/database/utils/workflowActionReconciliation'

/**
 * Controlled editor for a button field's ordered action list. Owns no state
 * beyond `value`: every mutation emits a new array and makes no API calls, so
 * the sub-form can discard changes by not saving.
 */
export default {
  name: 'ButtonFieldActionList',
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
  computed: {
    availableActionTypes() {
      return this.$registry.getOrderedList('databaseWorkflowActionType')
    },
  },
  methods: {
    actionTypeOf(action) {
      return this.$registry.get('databaseWorkflowActionType', action.type)
    },
    /**
     * What identifies a row of this list. An unsaved action has no id, and
     * its position cannot stand in for one: deleting the action above would
     * hand its identity, and so its form state, to the one below.
     */
    actionKey(action) {
      return action.id ?? action[CLIENT_ID_KEY]
    },
    /**
     * No type until the user picks one, and no `id` until the field is saved.
     */
    addAction(type = null) {
      this.$emit('input', [...this.value, this.newAction(type)])
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
