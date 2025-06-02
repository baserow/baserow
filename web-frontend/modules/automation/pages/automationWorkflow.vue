<template>
  <div class="automation-app">
    <AutomationHeader
      v-if="automation"
      :automation="automation"
      @read-only-toggled="handleReadOnlyToggle"
    />
    <div class="layout__col-2-2 automation-workflow__content">
      <div
        ref="editorRoot"
        :style="{
          width: activeSidePanel ? `calc(100% - ${sidePanelWidth}px)` : '100%',
        }"
      >
        <client-only>
          <WorkflowEditor
            :nodes="workflowNodes"
            :read-only="isWorkflowReadOnly"
            @add-node="handleAddNode"
            @click-node="handleClickNode"
            @remove-node="handleRemoveNode"
          />
        </client-only>
      </div>
      <div
        v-if="activeSidePanel"
        class="automation-workflow__side-panel"
        :style="{ width: sidePanelWidth + 'px' }"
      >
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
import WorkflowEditor from '@baserow/modules/automation/components/workflow/WorkflowEditor.vue'
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

    const handleAddNode = async ({ previousNodeId }) => {
      try {
        await store.dispatch('automationWorkflowNode/create', {
          workflow: currentWorkflow.value,
          type: 'rows_created',
          previousNodeId,
        })

        // Force a refresh of the workflow nodes by creating a new reference
        currentWorkflow.value = { ...currentWorkflow.value }
      } catch (err) {
        console.error('Failed to add node:', err)
      }
    }

    /**
     * When a node is clicked in `WorkflowNode`, ensure that the state
     * is updated in the store and the node is selected.
     * @param nodeId
     */
    const handleClickNode = (nodeId) => {
      if (nodeId) {
        const node = store.getters['automationWorkflowNode/findById'](
          currentWorkflow.value,
          nodeId
        )
        store.dispatch('automationWorkflowNode/select', {
          workflow: currentWorkflow.value,
          node,
        })
      } else {
        /**
         * When no node is selected, reset the active side panel to null,
         * this will close the side panel.
         */
        store.dispatch('automationWorkflow/setActiveSidePanel', null)
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

        // Force a refresh of the workflow nodes by creating a new reference
        currentWorkflow.value = { ...currentWorkflow.value }
      } catch (err) {
        console.error('Failed to delete node:', err)
      }
    }

    const activeSidePanel = computed(() => {
      return store.getters['automationWorkflow/getActiveSidePanel']
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
      handleClickNode,
      handleRemoveNode,
    }
  },
})
</script>
