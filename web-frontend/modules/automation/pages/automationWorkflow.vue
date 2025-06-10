<template>
  <div class="automation-app">
    <AutomationHeader
      v-if="automation"
      :automation="automation"
      @read-only-toggled="handleReadOnlyToggle"
    />
    <div class="layout__col-2-2 automation-workflow__content">
      <div class="automation-workflow__editor">
        <client-only>
          <WorkflowEditor
            v-model="selectedNodeId"
            :nodes="workflowNodes"
            :read-only="isWorkflowReadOnly"
            :is-adding-node="isAddingNode"
            @add-node="handleAddNode"
            @remove-node="handleRemoveNode"
          />
        </client-only>
      </div>

      <div v-if="activeSidePanel" class="automation-workflow__side-panel">
        <EditorSidePanels :active-side-panel="activeSidePanel" />
      </div>
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
import WorkflowEditor from '@baserow/modules/automation/components/workflow/WorkflowEditor'
import EditorSidePanels from '@baserow/modules/automation/components/workflow/EditorSidePanels'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'

export default defineComponent({
  name: 'AutomationWorkflow',
  components: {
    EditorSidePanels,
    AutomationHeader,
    WorkflowEditor,
  },
  layout: 'app',
  setup() {
    const store = useStore()
    const { params, error, app } = useContext()

    const automationId = parseInt(params.value.automationId)
    const workflowId = parseInt(params.value.workflowId)

    const workspace = ref(null)
    const automation = ref(null)
    const currentWorkflow = ref(null)
    const isAddingNode = ref(false)

    const sidePanelWidth = 360

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
        await store.dispatch('automationWorkflowNode/fetch', {
          workflow: currentWorkflow.value,
        })

        const applicationType = app.$registry.get(
          'application',
          AutomationApplicationType.getType()
        )
        await applicationType.loadExtraData(automation.value)

        currentWorkflow.value = { ...currentWorkflow.value }
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
      return store.getters['automationWorkflowNode/getNodes'](
        currentWorkflow.value
      )
    })

    const handleReadOnlyToggle = (newReadOnlyState) => {
      isWorkflowReadOnly.value = newReadOnlyState
    }

    const handleAddNode = async ({ type, previousNodeId }) => {
      try {
        isAddingNode.value = true
        await store.dispatch('automationWorkflowNode/create', {
          workflow: currentWorkflow.value,
          type,
          previousNodeId,
        })
      } catch (err) {
        console.error('Failed to add node:', err)
      } finally {
        isAddingNode.value = false
      }
    }

    const handleRemoveNode = async (nodeId) => {
      if (!currentWorkflow.value) {
        console.error('currentWorkflow is not available to remove a node.')
        return
      }
      try {
        await store.dispatch('automationWorkflowNode/delete', {
          workflow: currentWorkflow.value,
          nodeId: parseInt(nodeId),
        })

        currentWorkflow.value = { ...currentWorkflow.value }
      } catch (err) {
        console.error('Failed to delete node:', err)
      }
    }

    const activeSidePanel = computed(() => {
      return store.getters['automationWorkflow/getActiveSidePanel']
    })

    const selectedNodeId = computed({
      get() {
        const selectedNode = store.getters[
          'automationWorkflowNode/getSelected'
        ](currentWorkflow.value)
        return selectedNode?.id || null
      },
      set(nodeId) {
        let nodeToSelect = null
        if (nodeId) {
          nodeToSelect = store.getters['automationWorkflowNode/findById'](
            currentWorkflow.value,
            nodeId
          )
        }
        store.dispatch('automationWorkflowNode/select', {
          workflow: currentWorkflow.value,
          node: nodeToSelect,
        })
      },
    })

    return {
      workspace,
      automation,
      currentWorkflow,
      sidePanelWidth,
      isWorkflowReadOnly,
      workflowNodes,
      activeSidePanel,
      handleReadOnlyToggle,
      handleAddNode,
      handleRemoveNode,
      selectedNodeId,
      workflowId,
      isAddingNode,
    }
  },
})
</script>
