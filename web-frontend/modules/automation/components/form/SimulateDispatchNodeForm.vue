<template>
  <div class="simulate-dispatch-node">
    <Button
      :loading="isLoading"
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

    <div v-else-if="showTestNodeDescription">
      {{ $t('simulateDispatch.testNodeDescription') }}
    </div>

    <div v-else-if="isLoading">
      {{ $t('simulateDispatch.triggerNodeAwaitingEvent') }}
    </div>

    <div v-if="hasSampleData">
      <div class="simulate-dispatch-node__sample-data-label">
        {{ $t('simulateDispatch.sampleDataLabel') }}
      </div>
      <div class="simulate-dispatch-node__sample-data-code">
        <pre><code>{{ sampleData }}</code></pre>
      </div>
    </div>

    <Button
      v-if="sampleData"
      class="simulate-dispatch-node__button"
      type="secondary"
      icon="iconoir-code-brackets simulate-dispatch-node__button-icon"
      @click="showSampleDataModal"
    >
      {{ $t('simulateDispatch.buttonLabelShowPayload') }}
    </Button>

    <SampleDataModal
      ref="sampleDataModalRef"
      :sample-data="sampleData || {}"
      :title="sampleDataModalTitle"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import { inject, useContext, useStore } from '@nuxtjs/composition-api'
import { notifyIf } from '@baserow/modules/core/utils/error'
import SampleDataModal from '@baserow/modules/automation/components/sidebar/SampleDataModal'

const { app } = useContext()
const store = useStore()

const workflow = inject('workflow')
const sampleDataModalRef = ref(null)

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  automation: {
    type: Object,
    required: true,
  },
})

const isSimulating = computed(() => {
  return Number.isInteger(workflow.value.simulate_until_node_id)
})

const isSimulatingThisNode = computed(() => {
  return (
    isSimulating.value &&
    workflow.value.simulate_until_node_id === props.node.id
  )
})

const queryInProgress = ref(false)

const isLoading = computed(() => {
  return queryInProgress.value || isSimulatingThisNode.value
})

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

    if (!currentNode.service?.sample_data) {
      return app.i18n.t('simulateDispatch.errorPreviousNodesNotTested')
    }

    currentNode = workflow.value.orderedNodes.find(
      (node) => node.id === currentNode.previous_node_id
    )
  }

  return ''
})

const isDisabled = computed(() => {
  return (
    Boolean(nodeIsInError.value) ||
    (isSimulating.value && !isSimulatingThisNode.value)
  )
})

const sampleDataModalTitle = computed(() => {
  const nodeType = app.$registry.get('node', props.node.type)
  return app.i18n.t('simulateDispatch.sampleDataModalTitle', {
    nodeLabel: nodeType.getLabel({
      automation: props.automation,
      node: props.node,
    }),
  })
})

const sampleData = computed(() => {
  return props.node.service.sample_data?.data
})

const hasSampleData = computed(() => {
  return Boolean(sampleData.value)
})

const buttonLabel = computed(() => {
  return hasSampleData.value
    ? app.i18n.t('simulateDispatch.buttonLabelTestAgain')
    : app.i18n.t('simulateDispatch.buttonLabelTest')
})

const showTestNodeDescription = computed(() => {
  if (Boolean(nodeIsInError.value) || hasSampleData.value) {
    return false
  }

  return true
})

const simulateDispatchNode = async () => {
  queryInProgress.value = true

  try {
    await store.dispatch('automationWorkflowNode/simulateDispatch', {
      nodeId: props.node.id,
    })
  } catch (error) {
    notifyIf(error, 'automationWorkflow')
  }

  queryInProgress.value = false
}

const showSampleDataModal = () => {
  sampleDataModalRef.value.show()
}
</script>
