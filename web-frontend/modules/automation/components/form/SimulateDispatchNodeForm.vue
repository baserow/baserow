<template>
  <div class="simulate-dispatch-node">
    <Button
      :loading="isSimulatingDispatch"
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

    <div>{{ $t('simulateDispatch.testNodeDescription') }}</div>

    <div v-if="node.simulate_until_node && isTriggerNode">
      {{ $t('simulateDispatch.triggerNodeAwaitingEvent') }}
    </div>
    <div v-else-if="hasSampleData">
      <div class="simulate-dispatch-node__sample-data-label">
        {{ $t('simulateDispatch.sampleDataLabel') }}:
      </div>
      <pre><code class="simulate-dispatch-node__sample-data-code">{{ node.service.sample_data }}</code></pre>
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

  for (const node of workflow.value.orderedNodes) {
    const nodeType = app.$registry.get('node', node.type)

    if (node.order >= props.node.order) continue

    if (nodeType.isInError({ service: node.service })) {
      return app.i18n.t('simulateDispatch.errorPreviousNodeNotConfigured')
    }

    if (!node.service?.sample_data || node.simulate_until_node) {
      return app.i18n.t('simulateDispatch.errorPreviousNodesNotTested')
    }
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

const simulateDispatchNode = async () => {
  isSimulatingDispatch.value = true

  if (isTriggerNode.value) {
    isTestingTrigger.value = true
  }

  try {
    await store.dispatch('automationWorkflowNode/simulateDispatch', {
      nodeId: props.node.id,
      updateSampleData: true,
    })
  } catch (error) {
    notifyIf(error, 'automationWorkflow')
  }

  isSimulatingDispatch.value = false
}
</script>
