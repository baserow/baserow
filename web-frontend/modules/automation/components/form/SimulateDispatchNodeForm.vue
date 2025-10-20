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

    <div v-if="cantBeTestedReason">
      {{ cantBeTestedReason }}
    </div>

    <div v-else-if="showTestNodeDescription">
      {{ $t('simulateDispatch.testNodeDescription') }}
    </div>

    <div v-else-if="isLoading">
      {{ $t('simulateDispatch.triggerNodeAwaitingEvent') }}
    </div>

    <div v-if="hasSampleData && !isSimulating">
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

const automation = inject('automation')
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

const nodeType = computed(() => app.$registry.get('node', props.node.type))

const sampleData = computed(() => {
  const sample = nodeType.value.getSampleData(props.node)
  if (nodeType.value.serviceType.returnsList && sample) {
    return sample.results
  }
  return sample
})

const hasSampleData = computed(() => {
  return Boolean(sampleData.value)
})

/**
 * All previous nodes must have been tested, i.e. they must have sample
 * data and shouldn't be in error.
 */
const cantBeTestedReason = computed(() => {
  if (nodeType.value.isInError({ service: props.node.service })) {
    return app.i18n.t('simulateDispatch.errorNodeNotConfigured')
  }

  const previousNodes = store.getters[
    'automationWorkflowNode/getPreviousNodes'
  ](workflow.value, props.node)

  for (const previousNode of previousNodes) {
    const previousNodeType = app.$registry.get('node', previousNode.type)
    const nodeLabel = previousNodeType.getLabel({
      automation: automation.value,
      node: previousNode,
    })
    if (previousNodeType.isInError(previousNode)) {
      return app.i18n.t('simulateDispatch.errorPreviousNodeNotConfigured', {
        node: nodeLabel,
      })
    }

    if (!previousNodeType.getSampleData(previousNode)) {
      return app.i18n.t('simulateDispatch.errorPreviousNodesNotTested', {
        node: nodeLabel,
      })
    }
  }

  return ''
})

const isDisabled = computed(() => {
  return (
    Boolean(cantBeTestedReason.value) ||
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

const buttonLabel = computed(() => {
  return hasSampleData.value
    ? app.i18n.t('simulateDispatch.buttonLabelTestAgain')
    : app.i18n.t('simulateDispatch.buttonLabelTest')
})

const showTestNodeDescription = computed(() => {
  if (Boolean(cantBeTestedReason.value) || hasSampleData.value) {
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
