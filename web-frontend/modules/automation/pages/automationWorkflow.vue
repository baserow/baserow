<template>
  <div class="automation-app">
    <AutomationHeader
      :automation="automation"
      @read-only-toggled="handleReadOnlyToggle"
    />
    <div class="layout__col-2-2 automation-workflow__content">
      <client-only>
        <WorkflowEditor
          :nodes="workflowNodes"
          :read-only="isWorkflowReadOnly"
          @add-node="handleAddNode"
          @remove-node="handleRemoveNode"
        />
      </client-only>
    </div>
  </div>
</template>

<script>
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'
import WorkflowEditor from '@baserow/modules/automation/components/workflow/WorkflowEditor.vue'

export default {
  name: 'AutomationWorkflow',
  components: {
    AutomationHeader,
    WorkflowEditor,
  },
  provide() {
    return {
      workspace: this.workspace,
      automation: this.automation,
      currentWorkflow: this.currentWorkflow,
    }
  },
  layout: 'app',
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

      // Ensure the workflow exists before selecting and fetching nodes
      const workflow = store.getters['automationWorkflow/getById'](
        automation,
        workflowId
      )

      await store.dispatch('automationWorkflow/selectById', {
        automation,
        workflowId,
      })

      // Fetch the nodes for the selected workflow
      await store.dispatch('automationWorkflowNode/fetch', { workflowId })

      data.workspace = workspace
      data.automation = automation
      data.currentWorkflow = workflow
    } catch (e) {
      return error({
        statusCode: 404,
        message: 'Automation workflow or its nodes not found.', // Updated message
      })
    }
    return data
  },
  data() {
    return {
      isWorkflowReadOnly: false,
    }
  },
  computed: {
    workflowNodes() {
      // Assumes the store module is registered and nodes are fetched
      return this.$store.getters['automationWorkflowNode/getAll']
    },
  },
  methods: {
    handleReadOnlyToggle(newReadOnlyState) {
      this.isWorkflowReadOnly = newReadOnlyState
    },
    async handleAddNode({ type, previousNodeId }) {
      try {
        const newNode = await this.$store.dispatch(
          'automationWorkflowNode/create',
          {
            workflowId: this.currentWorkflow.id,
            type: 'row_created',
          }
        )

        if (!newNode || typeof newNode.id === 'undefined') {
          console.error(
            'Node creation failed or newNode object is invalid (id missing).',
            newNode
          )
          return
        }

        const newNodeIdString = newNode.id

        const currentNodesWithNew =
          this.$store.getters['automationWorkflowNode/getAll']

        const oldOrder = currentNodesWithNew.map((n) => n.id)

        const existingIds = currentNodesWithNew
          .filter((n) => n.id !== newNodeIdString)
          .map((n) => n.id)

        let newFinalOrderIds = []
        if (previousNodeId === null) {
          newFinalOrderIds = [newNodeIdString, ...existingIds]
        } else {
          const insertAfterIndex = existingIds.indexOf(previousNodeId)
          if (insertAfterIndex !== -1) {
            existingIds.splice(insertAfterIndex + 1, 0, newNodeIdString)
            newFinalOrderIds = existingIds
          } else {
            console.warn(
              `previousNodeId '${previousNodeId}'not found in existingIds (string array): [${existingIds.join(
                ', '
              )}]. Appending ${newNodeIdString}.`
            )
            newFinalOrderIds = [...existingIds, newNodeIdString]
          }
        }
        await this.$store.dispatch('automationWorkflowNode/order', {
          workflowId: this.currentWorkflow.id,
          order: newFinalOrderIds,
          oldOrder,
        })
      } catch (error) {
        console.error('Failed to add and order node:', error)
      }
    },
    async handleRemoveNode(nodeId) {
      try {
        await this.$store.dispatch('automationWorkflowNode/delete', {
          workflowId: this.currentWorkflow.id,
          nodeId: parseInt(nodeId),
        })
      } catch (error) {
        console.error('Failed to delete node:', error)
      }
    },
  },
}
</script>
