<template>
  <ABButton
    :loading="workflowActionsInProgress"
    @click="fireEvent(elementType.getEventByName(element, eventName))"
  >
    {{ labelWithDefault }}
  </ABButton>
</template>

<script>
import collectionField from '@baserow/modules/builder/mixins/collectionField'

export default {
  name: 'ButtonField',
  mixins: [collectionField],
  props: {
    label: {
      type: String,
      required: true,
    },
  },
  computed: {
    eventName() {
      return `${this.field.uid}_click`
    },
    workflowActionsInProgress() {
      const dispatchedById = this.elementType.uniqueElementId({
        element: this.element,
        applicationContext: this.applicationContext,
      })
      const workflowActions = this.$store.getters[
        'builderWorkflowAction/getElementWorkflowActions'
      ](this.elementPage, this.element.id)
      return workflowActions
        .filter((wa) => wa.event === this.eventName)
        .some((workflowAction) =>
          this.$store.getters['builderWorkflowAction/getDispatching'](
            workflowAction,
            dispatchedById
          )
        )
    },
    labelWithDefault() {
      if (this.label) {
        return this.label
      } else {
        return this.$t('buttonField.noLabel')
      }
    },
  },
}
</script>
