<template>
  <div>
    <Event
      v-for="event in elementType.getEvents(element)"
      :key="event.name"
      :element="element"
      :event="event"
      :available-workflow-action-types="availableWorkflowActionTypes"
      :workflow-actions="getWorkflowActionsForEvent(event)"
      :application-context-additions="event.applicationContextAdditions"
      class="margin-bottom-2"
    ></Event>
  </div>
</template>

<script>
import elementSidePanel from '@baserow/modules/builder/mixins/elementSidePanel'
import Event from '@baserow/modules/builder/components/event/Event.vue'
import { DATA_PROVIDERS_ALLOWED_WORKFLOW_ACTIONS } from '@baserow/modules/builder/enums'

export default {
  name: 'EventsSidePanel',
  components: { Event },
  mixins: [elementSidePanel],
  provide() {
    return {
      dataProvidersAllowed: DATA_PROVIDERS_ALLOWED_WORKFLOW_ACTIONS,
    }
  },
  computed: {
    availableWorkflowActionTypes() {
      return Object.values(this.$registry.getAll('workflowAction'))
    },
    workflowActions() {
      return this.$store.getters[
        'builderWorkflowAction/getElementWorkflowActions'
      ](this.elementPage, this.element.id)
    },
  },
  methods: {
    getWorkflowActionsForEvent(event) {
      return this.workflowActions.filter(
        (workflowAction) => workflowAction.event === event.name
      )
    },
  },
}
</script>
