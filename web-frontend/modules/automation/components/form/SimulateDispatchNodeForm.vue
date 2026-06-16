<template>
  <div v-if="!isReadOnly" class="simulate-dispatch-node">
    <Button
      :loading="isLoading"
      :disabled="isDisabled"
      class="simulate-dispatch-node__button"
      type="secondary"
      @click="simulateDispatchNode()"
    >
      {{ buttonLabel }}
    </Button>

    <Alert v-if="cantBeTestedReason" type="warning" class="margin-bottom-0">
      <p>{{ cantBeTestedReason }}</p>
    </Alert>

    <Alert
      v-if="isLoading"
      :type="nodeType.isTrigger ? 'warning' : 'info-neutral'"
    >
      <p>
        {{
          nodeType.isTrigger
            ? $t('simulateDispatch.triggerNodeAwaitingEvent')
            : $t('simulateDispatch.simulationInProgress')
        }}
      </p>
    </Alert>

    <Alert v-else-if="!hasSampleData" type="info-neutral">
      <p>
        {{ $t('simulateDispatch.testNodeDescription') }}
      </p>
    </Alert>

    <SampleDataViewer
      v-if="hasSampleData && !isLoading"
      :sample-data="sampleData"
      :is-error="isErrorSample"
      :modal-title="sampleDataModalTitle"
      :modal-subtitle="$t('simulateDispatch.sampleDataModalSubTitle')"
    />
  </div>
</template>

<script setup>
import { useStore } from 'vuex'
import { computed, ref } from 'vue'
import { notifyIf } from '@baserow/modules/core/utils/error'
import SampleDataViewer from '@baserow/modules/core/components/SampleDataViewer'

const { $i18n, $hasPermission, $registry } = useNuxtApp()
const store = useStore()

const workspace = inject('workspace')
const automation = inject('automation')
const workflow = inject('workflow')

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
})

const isReadOnly = computed(
  () =>
    !$hasPermission('automation.node.update', props.node, workspace.value.id)
)

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

const nodeType = computed(() => $registry.get('node', props.node.type))

const sample = computed(() => nodeType.value.getSampleData(props.node))

const sampleData = computed(() => {
  if (sample.value?._error) {
    return sample.value._error
  }
  if (nodeType.value.returnsList && sample.value?.data) {
    return sample.value.data.results
  }
  return sample.value?.data
})

// A node counts as tested once its service has a sample data envelope, even
// when the dispatch returned no data (e.g. a Read-a-row that matched no row,
// whose `data` is `null`). We therefore key this off the envelope's presence
// rather than the truthiness of its `data`.
const hasSampleData = computed(() => sample.value !== null)

const isErrorSample = computed(() => Boolean(sample.value?._error))

/**
 * All previous nodes must have been tested, i.e. they must have sample
 * data and shouldn't be in error.
 */
const cantBeTestedReason = computed(() => {
  if (
    nodeType.value.isInError({
      service: props.node.service,
      workspace: workspace.value,
    })
  ) {
    return $i18n.t('simulateDispatch.errorNodeNotConfigured')
  }

  const previousNodes = store.getters[
    'automationWorkflowNode/getPreviousNodes'
  ](workflow.value, props.node)

  for (const previousNode of previousNodes) {
    const previousNodeType = $registry.get('node', previousNode.type)
    const nodeLabel = previousNodeType.getLabel({
      automation: automation.value,
      node: previousNode,
    })
    if (
      previousNodeType.isInError({
        service: previousNode.service,
        workspace: workspace.value,
      })
    ) {
      return $i18n.t('simulateDispatch.errorPreviousNodeNotConfigured', {
        node: nodeLabel,
      })
    }

    // The node is considered tested once it has a sample data envelope and
    // didn't error, regardless of whether the dispatch returned any data.
    const previousSample = previousNodeType.getSampleData(previousNode)
    if (!previousSample || previousSample._error) {
      return $i18n.t('simulateDispatch.errorPreviousNodesNotTested', {
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
  const nodeType = $registry.get('node', props.node.type)
  return $i18n.t('simulateDispatch.sampleDataModalTitle', {
    nodeLabel: nodeType.getLabel({
      automation: automation.value,
      node: props.node,
    }),
  })
})

const buttonLabel = computed(() => {
  return hasSampleData.value
    ? $i18n.t('simulateDispatch.buttonLabelTestAgain')
    : $i18n.t('simulateDispatch.buttonLabelTest')
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
</script>
