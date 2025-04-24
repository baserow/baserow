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
          :pan-on-scroll="true"
        >
          <template #node-baserow="slotProps">
            <BaserowNode
              :id="slotProps.id"
              :type="slotProps.type"
              :data="slotProps.data"
              :label="slotProps.label"
              :selected="slotProps.selected"
              :dragging="slotProps.dragging"
              :connectable="slotProps.connectable"
              :position="slotProps.position"
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

import { ref } from 'vue'
import { initialEdges, initialNodes } from './initial-elements.js'
import {
  VueFlow,
  useVueFlow,
} from '@baserow/modules/automation/components/workflow/@vue-flow/core'

export default {
  name: 'AutomationWorkflow',
  components: { AutomationHeader, VueFlow, BaserowNode },
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

    onInit((vueFlowInstance) => {
      vueFlowInstance.fitView({ maxZoom: 1, minZoom: 1 })
    })

    onConnect((connection) => {
      addEdges(connection)
    })

    return {
      nodes,
      edges,
      nodesDraggable,
      zoomOnScroll,
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
