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
import {
  defineComponent,
  ref,
  computed,
  provide,
  useStore,
  useContext,
  useFetch,
} from '@nuxtjs/composition-api'
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'
import WorkflowEditor from '@baserow/modules/automation/components/workflow/WorkflowEditor.vue'

export default defineComponent({
  name: 'AutomationWorkflow',
  components: {
    AutomationHeader,
    WorkflowEditor,
  },
  layout: 'app',
  setup() {
    const store = useStore()
    const { params, error } = useContext()

    const automationId = parseInt(params.value.automationId)
    const workflowId = parseInt(params.value.workflowId)

    const workspace = ref(null)
    const automation = ref(null)
    const currentWorkflow = ref(null)

    useFetch(async () => {
      try {
        const fetchedAutomation = await store.dispatch(
          'application/selectById',
          automationId
        )
        automation.value = fetchedAutomation

        const fetchedWorkspace = await store.dispatch(
          'workspace/selectById',
          fetchedAutomation.workspace.id
        )
        workspace.value = fetchedWorkspace

        const fetchedWorkflow = store.getters['automationWorkflow/getById'](
          fetchedAutomation,
          workflowId
        )
        currentWorkflow.value = fetchedWorkflow

        await store.dispatch('automationWorkflow/selectById', {
          automation: fetchedAutomation,
          workflowId,
        })
        await store.dispatch('automationWorkflowNode/fetch', { workflowId })
      } catch (e) {
        return error({
          statusCode: 404,
          message: 'Automation workflow or its nodes not found.',
        })
      }
    })

    provide('workspace', workspace)
    provide('automation', automation)
    provide('currentWorkflow', currentWorkflow)

    const isWorkflowReadOnly = ref(false)
    const workflowNodes = computed(() => {
      return store.getters['automationWorkflowNode/getAll']
    })

    const handleReadOnlyToggle = (newReadOnlyState) => {
      isWorkflowReadOnly.value = newReadOnlyState
    }

    const handleAddNode = async ({ previousNodeId }) => {
      try {
        const newNode = await store.dispatch('automationWorkflowNode/create', {
          workflowId: currentWorkflow.value.id,
          type: 'row_created',
        })

        const newId = newNode.id

        const currentNodesIncludingNew =
          store.getters['automationWorkflowNode/getAll']
        const oldOrder = currentNodesIncludingNew.map((n) => n.id)

        const existingIds = currentNodesIncludingNew
          .filter((n) => n.id !== newId)
          .map((n) => n.id)

        let newFinalOrderIds = []
        if (previousNodeId === null) {
          newFinalOrderIds = [newId, ...existingIds]
        } else {
          const insertAfterIndex = existingIds.indexOf(previousNodeId)
          if (insertAfterIndex !== -1) {
            const tempExistingIds = [...existingIds]
            tempExistingIds.splice(insertAfterIndex + 1, 0, newId)
            newFinalOrderIds = tempExistingIds
          } else {
            console.warn(
              `previousNodeId '${previousNodeId}' not found in existingIds: [${existingIds.join(
                ', '
              )}]. Appending ${newId}.`
            )
            newFinalOrderIds = [...existingIds, newId]
          }
        }
        await store.dispatch('automationWorkflowNode/order', {
          workflowId: currentWorkflow.value.id,
          order: newFinalOrderIds,
          oldOrder,
        })
      } catch (err) {
        console.error('Failed to add and order node:', err)
      }
    }

    const handleRemoveNode = async (nodeId) => {
      if (!currentWorkflow.value) {
        console.error('currentWorkflow is not available to remove a node.')
        return
      }
      try {
        await store.dispatch('automationWorkflowNode/delete', {
          workflowId: currentWorkflow.value.id,
          nodeId: parseInt(nodeId),
        })
      } catch (err) {
        console.error('Failed to delete node:', err)
      }
    }

    return {
      workspace,
      automation,
      currentWorkflow,
      isWorkflowReadOnly,
      workflowNodes,
      handleReadOnlyToggle,
      handleAddNode,
      handleRemoveNode,
    }
  },
})
</script>
