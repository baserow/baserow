<template>
  <VueFlow
    class="workflow-editor"
    :nodes="vueFlowNodes"
    :edges="vueFlowEdges"
    :zoom-on-scroll="false"
    :nodes-draggable="false"
    :zoom-on-drag="zoomOnScroll"
    :pan-on-scroll="panOnScroll"
    :node-drag-threshold="2000"
    :zoom-on-double-click="zoomOnDoubleClick"
    fit-view-on-init
    :max-zoom="1"
    :min-zoom="0.5"
  >
    <Controls :show-interactive="false" />
    <Background pattern-color="#ededed" :size="3" :gap="15" />

    <template #node-workflow-node>
      <WorkflowNode
        v-if="trigger"
        :key="updateKey"
        :node="trigger"
        :debug="workflowDebug"
        :read-only="workflowReadOnly"
        :selected-node-id="selectedNodeId"
        @add-node="emit('add-node', $event)"
        @remove-node="emit('remove-node', $event)"
        @replace-node="emit('replace-node', $event)"
        @select-node="emit('input', $event.id)"
        @move-node="emit('move-node', $event)"
      />
      <div v-else :style="{ position: 'relative' }">
        <div ref="createTriggerContextAnchor" :style="{ position: 'relative' }">
          Choose a trigger
        </div>
        <WorkflowNodeContext
          ref="createTriggerContext"
          :only-trigger="true"
          @change="emit('add-node', { type: $event })"
        />
      </div>
    </template>
  </VueFlow>
</template>

<script setup>
import { VueFlow, useVueFlow } from '@vue2-flow/core'
import { Background } from '@vue2-flow/background'
import { Controls } from '@vue2-flow/controls'
import { ref, watch, toRefs, onMounted, nextTick } from 'vue'
import { inject, computed } from '@nuxtjs/composition-api'
import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode'
import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'

const props = defineProps({
  nodes: {
    type: Array,
    required: true,
  },
  value: {
    type: [String, Number],
    default: null,
  },
  isAddingNode: {
    type: Boolean,
    default: false,
  },
})

const vueFlowEdges = []
const emit = defineEmits(['add-node', 'remove-node', 'input', 'move-node'])

const { onPaneClick } = useVueFlow()

const { value: selectedNodeId } = toRefs(props)

const zoomOnScroll = ref(false)
const panOnScroll = ref(true)
const zoomOnDoubleClick = ref(false)
const updateKey = ref(1)

const createTriggerContext = ref(null)
const createTriggerContextAnchor = ref(null)

const workflow = inject('workflow')

const trigger = computed(() => {
  console.log('current graph', JSON.stringify(workflow.value.graph))
  if (workflow.value.graph['0']) {
    return props.nodes.find((node) => node.id === workflow.value.graph[0])
  }
  return null
})

const vueFlowNodes = computed(() => {
  return [
    {
      id: '1',
      type: 'workflow-node',
      selectable: false,
      position: { x: 0, y: 0 },
    },
  ]
})

const workflowDebug = inject('workflowDebug')
const workflowReadOnly = inject('workflowReadOnly')

const computedNodes = computed(() => {
  return props.nodes
})

/**
 * This watcher is used to force the update the workflow graph when nodes are updated.
 *  Vue-flow prevents the update somehow.
 */
watch(
  computedNodes,
  () => {
    updateKey.value += 1
  },
  { deep: true }
)

/**
 * When the component is mounted, we emit the first node's ID. This is
 * to ensure that the first node (the trigger) is selected by default.
 */
onMounted(async () => {
  if (props.nodes.length) {
    emit('input', props.nodes[0].id)
  } else {
    await nextTick()
    console.log(createTriggerContextAnchor.value)
    createTriggerContext.value.toggle(
      createTriggerContextAnchor.value,
      'bottom',
      'right',
      0
    )
  }
})

/**
 * When the pane is clicked, we emit `null` which
 * clears the selected node in the node store.
 */
onPaneClick(() => {
  emit('input', null)
})
</script>
