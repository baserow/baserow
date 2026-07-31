<template>
  <div class="button-field-action-list">
    <div
      v-for="(action, index) in value"
      :key="`${action.id ?? 'new'}-${index}`"
      v-sortable="{
        id: action.id ?? index,
        handle: '[data-sortable-handle]',
        update: onSortableUpdate,
      }"
      class="button-field-action-list__item margin-bottom-2"
    >
      <div class="flex align-items-center margin-bottom-1">
        <i
          class="iconoir-drag margin-right-1"
          style="cursor: grab"
          data-sortable-handle
        ></i>
        <Icon
          v-if="actionTypeOf(action).icon"
          :icon="actionTypeOf(action).icon"
          class="margin-right-1"
        />
        <div class="flex-grow-1">
          {{ actionTypeOf(action).label }}
        </div>
        <ButtonIcon
          icon="iconoir-bin"
          @click="removeAction(index)"
        ></ButtonIcon>
      </div>
      <DatabaseWorkflowActionWithService
        :workflow-action="action"
        :database="database"
        :default-values="action"
        @values-changed="onActionValuesChanged(index, $event)"
      />
    </div>

    <p v-if="value.length === 0" class="margin-bottom-2">
      {{ $t('buttonFieldActionList.empty') }}
    </p>

    <ButtonText
      ref="addActionButton"
      type="secondary"
      icon="iconoir-plus"
      @click="
        $refs.addActionContext.toggle(
          $refs.addActionButton.$el,
          'bottom',
          'left'
        )
      "
    >
      {{ $t('buttonFieldActionList.addAction') }}
    </ButtonText>
    <Context ref="addActionContext" :hide-on-click-outside="true">
      <div class="flex flex-wrap" style="--gap: 4px">
        <ButtonText
          v-for="actionType in availableActionTypes"
          :key="actionType.getType()"
          type="primary"
          size="small"
          :icon="actionType.icon"
          @click="onAddActionClicked(actionType)"
        >
          {{ actionType.label }}
        </ButtonText>
      </div>
    </Context>
  </div>
</template>

<script>
import _ from 'lodash'
import DatabaseWorkflowActionWithService from '@baserow/modules/database/components/field/DatabaseWorkflowActionWithService'

/**
 * Controlled editor for a button field's ordered action list. It owns no
 * state of its own beyond the `value` prop: every mutation emits a brand new
 * array via `input` and makes no API calls, so a field sub-form can discard
 * changes simply by not saving.
 *
 * Changing an existing action's type is intentionally not possible here. To
 * change type the user deletes the action and adds a new one, because the
 * reconciliation that turns this list into API calls only diffs an action's
 * `service`, never its `type`.
 */
export default {
  name: 'ButtonFieldActionList',
  components: { DatabaseWorkflowActionWithService },
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
    onAddActionClicked(actionType) {
      this.$refs.addActionContext.hide()
      this.addAction(actionType.getType())
    },
    /**
     * Adds a new action of the given type. New actions never carry an `id`:
     * that is only assigned once the field is saved and the backend creates
     * the underlying service.
     */
    addAction(type) {
      const newAction = { type, service: {} }
      this.$emit('input', [...this.value, newAction])
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
     * emit `input` when the service has genuinely changed to avoid spurious
     * updates.
     */
    onActionValuesChanged(index, values) {
      const action = this.value[index]
      if (_.isEqual(values.service, action.service)) {
        return
      }
      const newList = this.value.map((a, i) =>
        i === index ? { ...a, ...values } : a
      )
      this.$emit('input', newList)
    },
    onSortableUpdate(newOrder) {
      const bySortId = new Map(
        this.value.map((action, index) => [action.id ?? index, action])
      )
      this.orderActions(newOrder.map((id) => bySortId.get(id)))
    },
  },
}
</script>
