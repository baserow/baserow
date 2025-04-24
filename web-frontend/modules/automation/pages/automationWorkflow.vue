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
        >
        </VueFlow>
      </client-only>
    </div>
  </div>
</template>

<script>
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'
import { ref } from 'vue'
import { initialEdges, initialNodes } from './initial-elements.js'
import {
  VueFlow,
  useVueFlow,
} from '@baserow/modules/automation/components/workflow/@vue-flow/core'

export default {
  name: 'AutomationWorkflow',
  components: { AutomationHeader, VueFlow },
  provide() {
    return {
      workspace: this.workspace,
      automation: this.automation,
      currentWorkflow: this.currentWorkflow,
    }
  },
  layout: 'app',
  setup() {
    const { onInit, onNodeDragStop, onConnect, addEdges } = useVueFlow()

    const nodes = ref(initialNodes)
    const edges = ref(initialEdges)

    onInit((vueFlowInstance) => {
      // instance is the same as the return of `useVueFlow`
      vueFlowInstance.fitView()
    })

    onNodeDragStop(({ event, nodes, node }) => {
      console.log('Node Drag Stop', { event, nodes, node })
    })

    onConnect((connection) => {
      addEdges(connection)
    })

    // Retourner nodes et edges pour les rendre accessibles au template
    return {
      nodes,
      edges,
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
