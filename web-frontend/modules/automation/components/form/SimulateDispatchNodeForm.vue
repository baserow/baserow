<template>
  <div class="simulate-dispatch-node">
    <div class="simulate-dispatch-node__header">
      <div class="simulate-dispatch-node__header-title">
        <template v-if="isActionNode">{{
          $t('simulateDispatch.testActionNode')
        }}</template>
        <template v-else>{{ $t('simulateDispatch.testTriggerNode') }}</template>
      </div>

      <Button
        :loading="isSimulatingDispatch"
        :disabled="isDisabled"
        size="small"
        @click="simulateDispatchNode()"
      >
        {{ buttonLabel }}
      </Button>
    </div>

    <div v-if="nodeIsInError">
      {{ nodeIsInError }}
    </div>

    <div v-if="hasSampleData">
      <div class="simulate-dispatch-node__sample-data-label">
        {{ $t('simulateDispatch.sampleDataLabel') }}:
      </div>
      <pre><code class="simulate-dispatch-node__sample-data-code">{{ node.service.sample_data }}</code></pre>
    </div>
    <div v-else-if="node.simulate_dispatch_trigger">
      {{ $t('simulateDispatch.triggerNodeAwaitingEvent') }}
    </div>
    <div v-else>{{ $t('simulateDispatch.nodeNotTested') }}</div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import { inject, useContext, useStore } from '@nuxtjs/composition-api'
import { notifyIf } from '@baserow/modules/core/utils/error'

const { app } = useContext()
const store = useStore()

const workflow = inject('workflow')

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

    if (!node.service?.sample_data) {
      return app.i18n.t('simulateDispatch.errorPreviousNodesNotTested')
    }
  }

  return ''
})

const isDisabled = computed(() => {
  return (
    Boolean(nodeIsInError.value) ||
    isSimulatingDispatch.value ||
    (props.node.simulate_dispatch_trigger &&
      props.node.service.sample_data === null)
  )
})

const hasSampleData = computed(() => {
  return Boolean(props.node.service.sample_data)
})

const buttonLabel = computed(() => {
  return hasSampleData.value
    ? app.i18n.t('simulateDispatch.buttonLabelReTest')
    : app.i18n.t('simulateDispatch.buttonLabelTest')
})

const isActionNode = computed(() => {
  const nodeType = app.$registry.get('node', props.node.type)
  return nodeType.isWorkflowAction
})

const simulateDispatchNode = async () => {
  isSimulatingDispatch.value = true

  try {
    await store.dispatch('automationWorkflowNode/simulateDispatch', {
      nodeId: props.node.id,
      updateSampleData: hasSampleData.value,
    })
    await store.dispatch('automationWorkflowNode/fetchNodesAndSelect', {
      workflow: workflow.value,
    })
  } catch (error) {
    notifyIf(error, 'automationWorkflow')
  }

  isSimulatingDispatch.value = false
}
</script>
