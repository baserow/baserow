<template>
  <div class="button-field-action-list">
    <!--
      The sortable items need a parent of their own. The directive reads the
      new order off every element child of the dragged item's parent, so a
      sibling that is not an action — the add button below — would enter that
      order with no sortable id.
    -->
    <div class="button-field-action-list__items">
      <div
        v-for="(action, index) in value"
        :key="`${action.id ?? 'new'}-${index}`"
        v-sortable="{
          id: action.id ?? `new-${index}`,
          handle: '[data-sortable-handle]',
          update: onSortableUpdate,
        }"
        class="button-field-action-list__item margin-bottom-2"
      >
        <div class="button-field-action-list__header">
          <i
            class="iconoir-drag button-field-action-list__handle"
            data-sortable-handle
          ></i>
          <Dropdown
            class="button-field-action-list__type"
            :value="action.type ?? null"
            :placeholder="$t('buttonFieldActionList.chooseAction')"
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
              Keyed by type, not by the row: `create_row` and `update_row`
              resolve to the same form component and the same service form, and
              the row's own key does not change on a type swap, so Vue would
              reuse the instance and carry the old type's seeded values into a
              config that has just been reset.
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

    <p v-if="value.length === 0" class="margin-bottom-2">
      {{ $t('buttonFieldActionList.empty') }}
    </p>

    <ButtonText type="secondary" icon="iconoir-plus" @click="addAction()">
      {{ $t('buttonFieldActionList.addAction') }}
    </ButtonText>
  </div>
</template>

<script>
import _ from 'lodash'

/**
 * Controlled editor for a button field's ordered action list. It owns no
 * state of its own beyond the `value` prop: every mutation emits a brand new
 * array via `input` and makes no API calls, so a field sub-form can discard
 * changes simply by not saving.
 *
 * Each row picks its own type from a dropdown, so an existing action's type
 * can be changed in place. The reconciliation that turns this list into API
 * calls diffs `type` as well as the config, and the server implements a type
 * change as a delete plus a create that keeps the action's position.
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
     * Adds a new action. It carries no type until the user picks one from the
     * row's dropdown, and never carries an `id`: that is only assigned once
     * the field is saved and the backend creates the action.
     */
    addAction(type = null) {
      this.$emit('input', [...this.value, this.newAction(type)])
    },
    newAction(type) {
      if (type === null) {
        return { type: null }
      }
      return {
        type,
        ...this.$registry
          .get('databaseWorkflowActionType', type)
          .getNewActionValues(),
      }
    },
    /**
     * Swaps a row's type. The old type's config is dropped rather than merged:
     * it means nothing to the new type, and the server deletes and recreates
     * the action rather than converting it. The `id` is kept so the change is
     * reconciled as an update of the existing action, which is what preserves
     * its position.
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
     * The per-action form mounts its own default values on creation, which
     * emits `values-changed` once even when nothing actually changed. Only
     * emit `input` when the keys the form sent have genuinely changed, to
     * avoid spurious updates. Which keys those are depends on the type: a
     * service backed action sends `service`, `open_url` sends `url` and
     * `target`.
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
      // Unsaved actions have no id, so they fall back to an index-based key.
      // That fallback must be namespaced (`new-${index}`) so it can never
      // collide with a real id — otherwise a saved action and an unsaved one
      // could resolve to the same sortable id.
      const bySortId = new Map(
        this.value.map((action, index) => [action.id ?? `new-${index}`, action])
      )
      // An id with no action behind it would otherwise land in the list as
      // undefined and break the next render, taking the whole editor with it.
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
