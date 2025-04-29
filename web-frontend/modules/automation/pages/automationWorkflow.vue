<template>
  <div class="automation-app">
    <AutomationHeader :automation="automation" />
    <div class="layout__col-2-2 automation-app__content">
      <client-only>
        <VueFlow
          :nodes="nodes"
          :edges="edges"
          class="basic-flow"
          :zoom-on-scroll="false"
          :nodes-draggable="nodesDraggable"
          :zoom-on-drag="zoomOnScroll"
          :pan-on-scroll="panOnScroll"
          :zoom-on-double-click="zoomOnDoubleClick"
        >
          <template #node-baserow="slotProps">
            <BaserowNode
              :id="slotProps.id"
              :label="slotProps.label"
              :selected="slotProps.selected"
              :dragging="slotProps.dragging"
              :position="slotProps.position"
            />
          </template>

          <template #node-add="slotProps">
            <BaserowAddNode
              :id="slotProps.id"
              :label="slotProps.label"
              :selected="slotProps.selected"
              :dragging="slotProps.dragging"
              :position="slotProps.position"
              @addNode="onAddNode"
            />
          </template>

          <template #edge-baserow="slotProps">
            <BaserowEdge
              :id="slotProps.id"
              :source-x="slotProps.sourceX"
              :source-y="slotProps.sourceY"
              :target-x="slotProps.targetX"
              :target-y="slotProps.targetY"
            />
          </template>
        </VueFlow>
      </client-only>
    </div>
  </div>
</template>

<script>
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'
import BaserowNode from '@baserow/modules/automation/components/workflow/BaserowNode.vue'
import BaserowAddNode from '@baserow/modules/automation/components/workflow/BaserowAddNode.vue'
import BaserowEdge from '@baserow/modules/automation/components/workflow/BaserowEdge.vue'
import { ref } from 'vue'
import { initialEdges, initialNodes } from './initial-elements.js'
import {
  VueFlow,
  useVueFlow,
} from '@baserow/modules/automation/components/workflow/@vue-flow/core'

export default {
  name: 'AutomationWorkflow',
  components: {
    AutomationHeader,
    VueFlow,
    BaserowNode,
    BaserowEdge,
    BaserowAddNode,
  },
  provide() {
    return {
      workspace: this.workspace,
      automation: this.automation,
      currentWorkflow: this.currentWorkflow,
    }
  },
  layout: 'app',
  setup() {
    const { onInit, onConnect, addEdges } = useVueFlow()

    const nodes = ref(initialNodes)
    const edges = ref(initialEdges)
    const nodesDraggable = ref(false)
    const zoomOnScroll = ref(false)
    const panOnScroll = ref(true)
    const zoomOnDoubleClick = ref(false)

    onInit((vueFlowInstance) => {
      vueFlowInstance.fitView({ maxZoom: 1, minZoom: 1 })
    })

    onConnect((connection) => {
      addEdges(connection)
    })

    const onAddNode = (addNodeId) => {
      // Find the highest node ID and increment it
      const maxNodeId = Math.max(
        ...nodes.value.map((node) => parseInt(node.id, 10))
      )
      const newNodeId = (maxNodeId + 1).toString()

      // Find the clicked add node index
      const clickedNodeIndex = nodes.value.findIndex(
        (node) => node.id === addNodeId
      )
      if (clickedNodeIndex === -1) return

      // Find the source node that connects to this add node
      const sourceNodeId = edges.value.find(
        (edge) => edge.target === addNodeId
      )?.source

      // Calculate vertical position for the new node (144px below the source node)
      const sourceNode = nodes.value.find((node) => node.id === sourceNodeId)
      const newNodeY = sourceNode.position.y + 144

      // Create new baserow node
      const newNode = {
        id: newNodeId,
        label: 'New node',
        type: 'baserow',
        position: { x: 0, y: newNodeY },
      }

      // Create new add node below the new baserow node
      const newAddNodeId = (maxNodeId + 2).toString()
      const newAddNode = {
        id: newAddNodeId,
        label: '',
        type: 'add',
        position: { x: 190, y: newNodeY + 92 },
      }

      // Shift all nodes below the insertion point
      const nodesToShift = nodes.value.filter(
        (node) =>
          node.position.y > sourceNode.position.y && node.id !== addNodeId
      )

      nodesToShift.forEach((node) => {
        node.position.y += 144 // Shift by the height of two nodes (baserow + add)
      })

      // Create new edges to connect the nodes
      const newEdges = [
        // Edge from add node to new baserow node
        {
          id: `e${addNodeId}-${newNodeId}`,
          source: addNodeId,
          target: newNodeId,
          type: 'baserow',
        },
        // Edge from new baserow node to new add node
        {
          id: `e${newNodeId}-${newAddNodeId}`,
          source: newNodeId,
          target: newAddNodeId,
          type: 'baserow',
        },
      ]

      // Find next node that the clicked add node originally pointed to
      const nextNodeId = edges.value.find(
        (edge) => edge.source === addNodeId
      )?.target

      if (nextNodeId) {
        // Connect new add node to the next node
        newEdges.push({
          id: `e${newAddNodeId}-${nextNodeId}`,
          source: newAddNodeId,
          target: nextNodeId,
          type: 'baserow',
        })

        // Remove the original edge between clicked add node and next node
        const edgeToRemove = edges.value.findIndex(
          (edge) => edge.source === addNodeId && edge.target === nextNodeId
        )

        if (edgeToRemove !== -1) {
          edges.value.splice(edgeToRemove, 1)
        }
      }

      // Add the new nodes and edges
      nodes.value.push(newNode)
      nodes.value.push(newAddNode)
      edges.value.push(...newEdges)
    }

    return {
      nodes,
      edges,
      nodesDraggable,
      zoomOnScroll,
      panOnScroll,
      zoomOnDoubleClick,
      onAddNode,
    }
  },
  async asyncData({ store, params, error, $registry }) {
    const automationId = parseInt(params.automationId)
    const workflowId = parseInt(params.workflowId)

    const data = {}
    try {
      const automation = await store.dispatch(
        'application/selectById',
        automationId
      )
      const workspace = await store.dispatch(
        'workspace/selectById',
        automation.workspace.id
      )

      const workflow = store.getters['automationWorkflow/getById'](
        automation,
        workflowId
      )

      await store.dispatch('automationWorkflow/selectById', {
        automation,
        workflowId,
      })

      data.workspace = workspace
      data.automation = automation
      data.currentWorkflow = workflow
    } catch (e) {
      return error({
        statusCode: 404,
        message: 'Automation workflow not found.',
      })
    }
    return data
  },
}
</script>
