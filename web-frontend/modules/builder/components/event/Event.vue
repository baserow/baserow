<template>
  <div>
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
      <ButtonText
        ref="addWorkflowActionButton"
        type="secondary"
        icon="iconoir-plus"
        :loading="addingAction"
        @click="
          $refs.workflowActionAddContext.show(
            $refs.addWorkflowActionButton.$el,
            'bottom',
            'right'
          )
        "
      >
        {{ $t('event.addAction') }}
      </ButtonText>
      <Context ref="workflowActionAddContext" :hide-on-click-outside="true">
        <div class="event__add-action-context">
          <ButtonText
            v-for="workflowActionType in availableWorkflowActionTypes"
            :key="workflowActionType.getType()"
            :value="workflowActionType.getType()"
            :icon="workflowActionType.icon"
            :image="workflowActionType.image"
            type="primary"
            size="small"
            @click="addWorkflowAction(workflowActionType.getType())"
          >
            {{ workflowActionType.label }}
          </ButtonText>
        </div>
      </Context>
    </div>
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
        :expanded="expanded[workflowAction.id]"
        :class="{ 'event__workflow-action--first': index === 0 }"
        :element="element"
        :available-workflow-action-types="availableWorkflowActionTypes"
        :workflow-action="workflowAction"
        :workflow-action-index="index"
        :application-context-additions="{ workflowAction }"
        @toggle="onToggle(workflowAction)"
        @delete="deleteWorkflowAction(workflowAction)"
      />
    </div>
  </div>
</template>

<script>
import { mapActions } from 'vuex'
import { Event } from '@baserow/modules/builder/eventTypes'
import WorkflowAction from '@baserow/modules/builder/components/event/WorkflowAction'
import applicationContext from '@baserow/modules/builder/mixins/applicationContext'
import { notifyIf } from '@baserow/modules/core/utils/error'

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
      expanded: {},
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
      actionCreateWorkflowAction: 'builderWorkflowAction/create',
      actionDeleteWorkflowAction: 'builderWorkflowAction/delete',
      actionOrderWorkflowActions: 'builderWorkflowAction/order',
    }),
    /*
    We keep the expanded state at the event level because of the :key it's not working
    as expected
    */
    onToggle(workflow) {
      this.expanded = {
        ...this.expanded,
        [workflow.id]: !this.expanded[workflow.id],
      }
    },
    async addWorkflowAction(type) {
      this.addingAction = true
      this.$refs.workflowActionAddContext.hide()
      try {
        await this.actionCreateWorkflowAction({
          page: this.elementPage,
          workflowActionType: type,
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
