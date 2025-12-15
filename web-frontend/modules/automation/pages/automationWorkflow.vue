<template>
  <div class="automation-workflow">
    <AutomationHeader
      v-if="automation"
      :automation="automation"
      @read-only-toggled="handleReadOnlyToggle"
      @debug-toggled="handleDebugToggle"
    />
    <div
      class="layout__col-2-2 automation-workflow__content"
      :class="{
        'automation-workflow__content--loading': workflowLoading,
      }"
    >
      <div v-if="workflowLoading" class="loading"></div>
      <div
        v-else
        class="automation-workflow__editor"
        data-highlight="automation-editor"
      >
        <client-only>
          <WorkflowEditor
            v-model="selectedNodeId"
            :nodes="workflowNodes"
            :is-adding-node="isAddingNode"
            @add-node="handleAddNode"
            @remove-node="handleRemoveNode"
            @replace-node="handleReplaceNode"
            @move-node="handleMoveNode"
            @duplicate-node="handleDuplicateNode"
          />
        </client-only>
      </div>
      <div v-if="activeSidePanel" class="automation-workflow__side-panel">
        <EditorSidePanels
          :active-side-panel="activeSidePanel"
          :data-highlight="activeSidePanelType?.guidedTourAttr"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, provide } from 'vue'
import { useAsyncData } from '#imports'
import { onBeforeRouteUpdate, onBeforeRouteLeave } from 'vue-router'

import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'
import WorkflowEditor from '@baserow/modules/automation/components/workflow/WorkflowEditor'
import EditorSidePanels from '@baserow/modules/automation/components/workflow/EditorSidePanels'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { StoreItemLookupError } from '@baserow/modules/core/errors'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})

const route = useRoute()
const { $store, $registry } = useNuxtApp()

// Local state
const isAddingNode = ref(false)
const workflowLoading = ref(false)
const sidePanelWidth = ref(360)
const workflowReadOnly = ref(false)
const workflowDebug = ref(false)

// Load page data
const { data: pageData } = await useAsyncData(
  () =>
    `automation-workflow-${route.params.automationId}-${route.params.workflowId}`,
  async () => {
    const automationId = parseInt(route.params.automationId)
    const workflowId = parseInt(route.params.workflowId)

    try {
      const loadedAutomation = await $store.dispatch(
        'application/selectById',
        automationId
      )

      const loadedWorkspace = await $store.dispatch(
        'workspace/selectById',
        loadedAutomation.workspace.id
      )

      const loadedWorkflow = await $store.dispatch(
        'automationWorkflow/selectById',
        {
          automation: loadedAutomation,
          workflowId,
        }
      )

      await $store.dispatch('automationHistory/fetchWorkflowHistory', {
        workflowId,
      })

      await $store.dispatch('automationWorkflowNode/fetch', {
        workflow: loadedWorkflow,
      })

      const applicationType = $registry.get(
        'application',
        AutomationApplicationType.getType()
      )
      await applicationType.loadExtraData(loadedAutomation)

      return {
        automation: loadedAutomation,
        workspace: loadedWorkspace,
        workflow: loadedWorkflow,
      }
    } catch (e) {
      throw createError({
        statusCode: 404,
        message: 'Automation workflow not found.',
      })
    }
  }
)

// Computed properties from async data
const automation = computed(() => pageData.value?.automation ?? null)
const workspace = computed(() => pageData.value?.workspace ?? null)
const workflow = computed(() => pageData.value?.workflow ?? null)

// Computed properties
const isDev = computed(() => process.env.NODE_ENV === 'development')

const workflowNodes = computed(() => {
  if (!workflow.value) {
    return []
  }
  return $store.getters['automationWorkflowNode/getNodes'](workflow.value)
})

const activeSidePanel = computed(() => {
  return $store.getters['automationWorkflow/getActiveSidePanel']
})

const activeSidePanelType = computed(() => {
  return activeSidePanel.value
    ? $registry.get('editorSidePanel', activeSidePanel.value)
    : null
})

const selectedNodeId = computed({
  get() {
    return workflow.value ? workflow.value.selectedNodeId : null
  },
  set(nodeId) {
    let nodeToSelect = null
    if (nodeId) {
      nodeToSelect = $store.getters['automationWorkflowNode/findById'](
        workflow.value,
        nodeId
      )
    }
    $store.dispatch('automationWorkflowNode/select', {
      workflow: workflow.value,
      node: nodeToSelect,
    })
  },
})

// Provide values for child components
provide('isDev', isDev)
provide('workspace', workspace)
provide('automation', automation)
provide('workflow', workflow)
provide('workflowReadOnly', workflowReadOnly)
provide('workflowDebug', workflowDebug)

// Methods
function handleReadOnlyToggle(newReadOnlyState) {
  workflowReadOnly.value = newReadOnlyState
}

function handleDebugToggle(newDebugState) {
  workflowDebug.value = newDebugState
}

async function handleAddNode({ type, referenceNode, position, output }) {
  try {
    isAddingNode.value = true
    await $store.dispatch('automationWorkflowNode/create', {
      workflow: workflow.value,
      type,
      referenceNode,
      position,
      output,
    })
  } catch (err) {
    console.error('Failed to add node:', `${err}`)
    notifyIf(err, 'automation')
  } finally {
    isAddingNode.value = false
  }
}

async function handleRemoveNode(nodeId) {
  if (!workflow.value) {
    return
  }
  try {
    await $store.dispatch('automationWorkflowNode/delete', {
      workflow: workflow.value,
      nodeId: parseInt(nodeId),
    })
  } catch (err) {
    console.error('Failed to delete node:', err)
    notifyIf(err, 'automation')
  }
}

async function handleReplaceNode({ node, type }) {
  try {
    await $store.dispatch('automationWorkflowNode/replace', {
      workflow: workflow.value,
      nodeId: parseInt(node.id),
      newType: type,
    })
  } catch (err) {
    console.error('Failed to replace node:', err)
    notifyIf(err, 'automation')
  }
}

async function handleMoveNode(moveData) {
  const movedNodeId = $store.getters['automationWorkflowNode/getDraggingNodeId']

  $store.dispatch('automationWorkflowNode/setDraggingNodeId', null)

  if (!movedNodeId) {
    return
  }
  try {
    await $store.dispatch('automationWorkflowNode/move', {
      workflow: workflow.value,
      moveData: {
        movedNodeId,
        ...moveData,
      },
    })
  } catch (err) {
    console.error('Failed to move node:', err)
    notifyIf(err, 'automation')
  }
}

async function handleDuplicateNode(nodeId) {
  await $store.dispatch('automationWorkflowNode/duplicate', {
    workflow: workflow.value,
    nodeId,
  })
}

function onRouteChange(from) {
  const currentAutomation = $store.getters['application/get'](
    parseInt(from.params.automationId)
  )
  if (currentAutomation) {
    try {
      const currentWorkflow = $store.getters['automationWorkflow/getById'](
        currentAutomation,
        parseInt(from.params.workflowId)
      )

      $store.dispatch('automationWorkflowNode/select', {
        workflow: currentWorkflow,
        node: null,
      })
      $store.dispatch('application/forceUpdate', {
        application: currentAutomation,
        data: { _loadedOnce: false },
      })
    } catch (e) {
      if (!(e instanceof StoreItemLookupError)) {
        throw e
      }
    }
  }
}

// Navigation guards
onBeforeRouteUpdate((to, from) => {
  onRouteChange(from)
})

onBeforeRouteLeave((to, from) => {
  $store.dispatch('automationWorkflow/unselect')
  onRouteChange(from)
})
</script>
