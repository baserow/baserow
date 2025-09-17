<template>
  <div class="simulate-dispatch-node">
    <Button
      :loading="isSimulatingDispatch || isAwaitingTriggerEvent"
      :disabled="isDisabled"
      class="simulate-dispatch-node__button"
      type="secondary"
      @click="simulateDispatchNode()"
    >
      {{ buttonLabel }}
    </Button>

    <div v-if="nodeIsInError">
      {{ nodeIsInError }}
    </div>

    <div v-if="showTestNodeDescription">
      {{ $t('simulateDispatch.testNodeDescription') }}
    </div>

    <div v-if="isAwaitingTriggerEvent">
      {{ $t('simulateDispatch.triggerNodeAwaitingEvent') }}
    </div>
    <div v-else-if="hasSampleData">
      <div class="simulate-dispatch-node__sample-data-label">
        {{ $t('simulateDispatch.sampleDataLabel') }}:
      </div>
      <pre><code class="simulate-dispatch-node__sample-data-code">{{ sampleData }}</code></pre>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import { inject, useContext, useStore } from '@nuxtjs/composition-api'
import { notifyIf } from '@baserow/modules/core/utils/error'

const { app } = useContext()
const store = useStore()

const workflow = inject('workflow')
const isTestingTrigger = ref(false)

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
})

const isSimulatingDispatch = ref(false)

/**
 * All previous nodes must have been tested, i.e. they must have sample
 * data and shouldn't be in error.
 */
const nodeIsInError = computed(() => {
  const nodeType = app.$registry.get('node', props.node.type)
  if (nodeType.isInError({ service: props.node.service })) {
    return app.i18n.t('simulateDispatch.errorNodeNotConfigured')
  }

  let currentNode = workflow.value.orderedNodes.find(
    (node) => node.id === props.node.previous_node_id
  )

  while (currentNode) {
    const nodeType = app.$registry.get('node', currentNode.type)

    if (nodeType.isInError({ service: currentNode.service })) {
      return app.i18n.t('simulateDispatch.errorPreviousNodeNotConfigured')
    }

    if (!currentNode.service?.sample_data || currentNode.simulate_until_node) {
      return app.i18n.t('simulateDispatch.errorPreviousNodesNotTested')
    }

    currentNode = workflow.value.orderedNodes.find(
      (node) => node.id === currentNode.previous_node_id
    )
  }

  return ''
})

const isTriggerNode = computed(() => {
  const nodeType = app.$registry.get('node', props.node.type)
  return Boolean(nodeType.isTrigger)
})

const isDisabled = computed(() => {
  return (
    Boolean(nodeIsInError.value) ||
    isSimulatingDispatch.value ||
    props.node.simulate_until_node ||
    (isTriggerNode.value && isTestingTrigger.value)
  )
})

const hasSampleData = computed(() => {
  return Boolean(props.node.service.sample_data)
})

const buttonLabel = computed(() => {
  return hasSampleData.value
    ? app.i18n.t('simulateDispatch.buttonLabelTestAgain')
    : app.i18n.t('simulateDispatch.buttonLabelTest')
})

const sampleData = computed(() => {
  const data = props.node.service.sample_data?.data
  if (data) {
    if (data?.body) {
      return props.node.service.sample_data.data.body
    } else {
      return props.node.service.sample_data.data
    }
  }

  return props.node.service.sample_data
})

const isAwaitingTriggerEvent = computed(() => {
  return props.node.simulate_until_node && isTriggerNode.value
})

const showTestNodeDescription = computed(() => {
  if (
    Boolean(nodeIsInError.value) ||
    isAwaitingTriggerEvent.value ||
    hasSampleData.value
  ) {
    return false
  }

  return true
})

const simulateDispatchNode = async () => {
  isSimulatingDispatch.value = true

  if (isTriggerNode.value) {
    isTestingTrigger.value = true
  }

  try {
    await store.dispatch('automationWorkflowNode/simulateDispatch', {
      workflow: workflow.value,
      nodeId: props.node.id,
      updateSampleData: true,
    })
  } catch (error) {
    notifyIf(error, 'automationWorkflow')
  }

  isSimulatingDispatch.value = false
}
</script>
