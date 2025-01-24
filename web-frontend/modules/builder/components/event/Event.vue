<template>
  <Expandable toggle-on-click :default-expanded="workflowActions.length < 2">
    <template #header="{ expanded }">
      <div class="event__header">
        <div class="event__header-left">
          <div class="event__label">
            {{ event.label }}
          </div>
          <div
            v-if="workflowActions.length"
            class="margin-left-1 event__amount-actions"
          >
            {{ workflowActions.length }}
          </div>
        </div>
        <a class="event__toggle">
          <i :class="getIcon(expanded)"></i>
        </a>
      </div>
    </template>
    <template #default>
      <div>
        <!--
          By setting the WorkflowAction 'key' property to '$id_$order_$workflow.length'
          we ensure that the component is re-rendered once that value changes.
          This value will change after an action is ordered, thus triggering the
          rendering engine, which can be useful when we want instant visual
          feedback.
          One example would be to highlight formulas that become invalid after
          action ordering.
        -->
        <WorkflowAction
          v-for="(workflowAction, index) in workflowActions"
          :key="`${workflowAction.id}_${workflowAction.order}_${workflowActions.length}`"
          v-sortable="{
            id: workflowAction.id,
            handle: '[data-sortable-handle]',
            update: orderWorkflowActions,
            enabled: $hasPermission(
              'builder.page.element.update',
              element,
              workspace.id
            ),
          }"
          class="event__workflow-action"
          :class="{ 'event__workflow-action--first': index === 0 }"
          :element="element"
          :available-workflow-action-types="availableWorkflowActionTypes"
          :workflow-action="workflowAction"
          :workflow-action-index="index"
          :application-context-additions="{ workflowAction }"
          @delete="deleteWorkflowAction(workflowAction)"
        />
      </div>
      <ButtonText
        type="secondary"
        icon="iconoir-plus"
        :loading="addingAction"
        @click="addWorkflowAction"
      >
        {{ $t('event.addAction') }}
      </ButtonText>
    </template>
  </Expandable>
</template>

<script>
import { Event } from '@baserow/modules/builder/eventTypes'
import WorkflowAction from '@baserow/modules/core/components/workflowActions/WorkflowAction'
import { NotificationWorkflowActionType } from '@baserow/modules/builder/workflowActionTypes'
import { mapActions } from 'vuex'
import applicationContext from '@baserow/modules/builder/mixins/applicationContext'
import { notifyIf } from '@baserow/modules/core/utils/error'

const DEFAULT_WORKFLOW_ACTION_TYPE = NotificationWorkflowActionType.getType()

export default {
  name: 'Event',
  components: { WorkflowAction },
  mixins: [applicationContext],
  inject: ['workspace', 'builder', 'elementPage'],
  props: {
    event: {
      type: Event,
      required: true,
    },
    element: {
      type: Object,
      required: true,
    },
    workflowActions: {
      type: Array,
      required: false,
      default: () => [],
    },
    availableWorkflowActionTypes: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      addingAction: false,
    }
  },
  async mounted() {
    try {
      await Promise.all([
        this.actionFetchIntegrations({
          application: this.builder,
        }),
      ])
    } catch (error) {
      notifyIf(error)
    }
  },
  methods: {
    ...mapActions({
      actionFetchIntegrations: 'integration/fetch',
      actionCreateWorkflowAction: 'workflowAction/create',
      actionDeleteWorkflowAction: 'workflowAction/delete',
      actionOrderWorkflowActions: 'workflowAction/order',
    }),
    getIcon(expanded) {
      return expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'
    },
    async addWorkflowAction() {
      this.addingAction = true
      try {
        await this.actionCreateWorkflowAction({
          page: this.elementPage,
          workflowActionType: DEFAULT_WORKFLOW_ACTION_TYPE,
          eventType: this.event.name,
          configuration: {
            element_id: this.element.id,
          },
        })
      } catch (error) {
        notifyIf(error)
      }
      this.addingAction = false
    },
    async deleteWorkflowAction(workflowAction) {
      try {
        await this.actionDeleteWorkflowAction({
          page: this.elementPage,
          workflowAction,
        })
      } catch (error) {
        notifyIf(error)
      }
    },
    async orderWorkflowActions(order) {
      try {
        await this.actionOrderWorkflowActions({
          page: this.elementPage,
          element: this.element,
          order,
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
