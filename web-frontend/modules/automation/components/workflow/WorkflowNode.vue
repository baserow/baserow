<template>
  <div ref="workflowNode" class="workflow-node">
    <WorkflowNodeContent
      ref="nodeComponent"
      :node="node"
      :data-highlight="
        node.previous_node_id === null
          ? 'automation-trigger'
          : 'automation-action'
      "
      :selected="node.id === selectedNodeId"
      :debug="debug"
      :read-only="readOnly"
      @select-node="emit('select-node', $event)"
      @remove-node="emit('remove-node', $event)"
      @replace-node="emit('replace-node', $event)"
    />
    <WorkflowConnector
      v-for="coords in coordsPerEdge"
      :key="coords[0]"
      :coords="coords[1]"
    />
    <div class="workflow-node__edges">
      <div
        v-for="edge in nodeEdges"
        :ref="`edge-${edge.uid}`"
        :key="edge.uid"
        class="workflow-node__edge"
      >
        <WorkflowEdge
          :node="node"
          :edge="edge"
          :has-siblings="nodeEdges.length > 1"
          :selected-node-id="selectedNodeId"
          :debug="debug"
          :read-only="readOnly"
          @add-node="emit('add-node', $event)"
          @select-node="emit('select-node', $event)"
          @remove-node="emit('remove-node', $event)"
          @replace-node="emit('replace-node', $event)"
          @move-node="emit('move-node', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  useContext,
  computed,
  getCurrentInstance,
} from '@nuxtjs/composition-api'
import WorkflowNodeContent from '@baserow/modules/automation/components/workflow/WorkflowNodeContent'
import WorkflowEdge from '@baserow/modules/automation/components/workflow/WorkflowEdge'
import WorkflowConnector from '@baserow/modules/automation/components/workflow/WorkflowConnector'

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  selectedNodeId: {
    type: Number,
    required: false,
    default: null,
  },
  debug: {
    type: Boolean,
    default: false,
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'add-node',
  'select-node',
  'remove-node',
  'replace-node',
  'move-node',
])

const { app } = useContext()

const instance = getCurrentInstance()
const refs = instance.proxy.$refs

const workflowNode = ref()
const nodeComponent = ref()

const nodeType = computed(() => app.$registry.get('node', props.node.type))
const nodeEdges = computed(() => nodeType.value.getEdges({ node: props.node }))

/**
 * Compute all connector coordinates per edge
 */
const coordsPerEdge = computed(() => {
  if (!workflowNode.value || !nodeComponent.value) return []

  return nodeEdges.value.map((edge) => {
    const wrap = workflowNode.value
    const elt = nodeComponent.value.$el

    const edgeElt = refs[`edge-${edge.uid}`][0]

    const startX = edgeElt.offsetLeft + edgeElt.offsetWidth / 2
    const startY = elt.offsetHeight + 40
    const endX = wrap.offsetWidth / 2
    const endY = elt.offsetHeight

    return [edge.uid, { startX, startY, endY, endX }]
  })
})
</script>
