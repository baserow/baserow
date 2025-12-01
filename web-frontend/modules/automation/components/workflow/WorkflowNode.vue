<template>
  <div ref="workflowNode" class="workflow-node">
    <WorkflowNodeContent
      ref="nodeComponent"
      :node="node"
      :data-highlight="
        nodeType.is_workflow_trigger
          ? 'automation-trigger'
          : 'automation-action'
      "
      :selected="node.id === selectedNodeId"
      :debug="debug"
      :read-only="readOnly"
      @select-node="emit('select-node', $event)"
      @remove-node="emit('remove-node', $event)"
      @replace-node="emit('replace-node', $event)"
      @duplicate-node="emit('duplicate-node', $event)"
    />
    <div v-if="nodeType.isContainer" class="workflow-node__children">
      <div ref="children" class="workflow-node__children-wrapper">
        <div class="workflow-node__connectors">
          <WorkflowConnector :coords="childEdgeCoords" />
        </div>
        <div class="workflow-node__edges">
          <WorkflowEdge
            ref="child-edge"
            class="workflow-node__edge"
            :node="node"
            :is-child="true"
            :has-siblings="false"
            :selected-node-id="selectedNodeId"
            :debug="debug"
            :read-only="readOnly"
            @add-node="emit('add-node', $event)"
            @select-node="emit('select-node', $event)"
            @remove-node="emit('remove-node', $event)"
            @replace-node="emit('replace-node', $event)"
            @move-node="emit('move-node', $event)"
            @duplicate-node="emit('duplicate-node', $event)"
          />
        </div>
      </div>
    </div>
    <div
      class="workflow-node__connectors"
      :class="{ 'workflow-node__connectors--multiple': hasMultipleEdges }"
    >
      <WorkflowConnector
        v-for="coords in coordsPerEdge"
        :key="coords[0]"
        :coords="coords[1]"
      />
    </div>
    <div class="workflow-node__edges">
      <WorkflowEdge
        v-for="edge in nodeEdges"
        :ref="`edge-${edge.uid}`"
        :key="edge.uid"
        class="workflow-node__edge"
        :node="node"
        :edge-uid="edge.uid"
        :edge-label="edge.label"
        :has-siblings="nodeEdges.length > 1"
        :selected-node-id="selectedNodeId"
        :debug="debug"
        :read-only="readOnly"
        @add-node="emit('add-node', $event)"
        @select-node="emit('select-node', $event)"
        @remove-node="emit('remove-node', $event)"
        @replace-node="emit('replace-node', $event)"
        @move-node="emit('move-node', $event)"
        @duplicate-node="emit('duplicate-node', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import {
  useContext,
  computed,
  getCurrentInstance,
} from '@nuxtjs/composition-api'
import WorkflowNodeContent from '@baserow/modules/automation/components/workflow/WorkflowNodeContent'
import WorkflowEdge from '@baserow/modules/automation/components/workflow/WorkflowEdge'
import WorkflowConnector from '@baserow/modules/automation/components/workflow/WorkflowConnector'

const connectorHeight = 32

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
  'duplicate-node',
])

const { app } = useContext()

const instance = getCurrentInstance()
const refs = instance.proxy.$refs

const workflowNode = ref()
const children = ref()
const nodeComponent = ref()
const coordsPerEdge = ref([])

const nodeType = computed(() => app.$registry.get('node', props.node.type))
const nodeEdges = computed(() => nodeType.value.getEdges({ node: props.node }))

const hasMultipleEdges = computed(() => nodeEdges.value.length > 1)

const computeEdgeCoords = (wrapper, edgeElt, multiple = false) => {
  const startX = edgeElt.offsetLeft + edgeElt.offsetWidth / 2
  const endX = wrapper.offsetWidth / 2

  const startY = multiple ? connectorHeight * 2 : connectorHeight
  const endY = 0

  return { startX, endX, startY, endY }
}

/**
 * Compute all connector coordinates per edge on edge changes
 */
watch(
  nodeEdges,
  async () => {
    await nextTick()
    coordsPerEdge.value = nodeEdges.value.map((edge) => {
      const wrap = workflowNode.value
      if (Array.isArray(refs[`edge-${edge.uid}`])) {
        const edgeElt = refs[`edge-${edge.uid}`][0].$el

        return [
          edge.uid,
          computeEdgeCoords(wrap, edgeElt, hasMultipleEdges.value),
        ]
      } else {
        // We might have a delay between the edge addition
        // and the branch being visible
        return [edge.uid, { startX: 0, startY: 0, endX: 0, endY: 0 }]
      }
    })
  },
  { immediate: true }
)

const childEdgeCoords = computed(() => {
  if (nodeType.value.isContainer) {
    if (!children.value) return { startX: 0, startY: 0, endX: 0, endY: 0 }

    const wrap = children.value
    const edgeElt = refs['child-edge'].$el

    return computeEdgeCoords(wrap, edgeElt)
  }
  return null
})
</script>
