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
      const { recordIndexPath } = this.applicationContext
      const dispatchedById = this.elementType.uniqueElementId(
        this.element,
        recordIndexPath
      )
      const workflowActions = this.$store.getters[
        'workflowAction/getElementWorkflowActions'
      ](this.elementPage, this.element.id)
      return workflowActions
        .filter((wa) => wa.event === this.eventName)
        .some((workflowAction) =>
          this.$store.getters['workflowAction/getDispatching'](
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
