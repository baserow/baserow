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

const { t } = useI18n()

useHead(() => ({
  title: t('automationWorkflow.title'),
}))

const route = useRoute()
const { $store, $registry } = useNuxtApp()

// Parse route params once at setup time
const automationId = computed(() => {
  const param = route.params.automationId
  if (typeof param === 'string') {
    return parseInt(param, 10)
  }
  if (typeof param === 'number') {
    return param
  }
  return null
})

const workflowId = computed(() => {
  const param = route.params.workflowId
  if (typeof param === 'string') {
    return parseInt(param, 10)
  }
  if (typeof param === 'number') {
    return param
  }
  return null
})

// Local state
const isAddingNode = ref(false)
const workflowLoading = ref(false)
const sidePanelWidth = ref(360)
const workflowReadOnly = ref(false)
const workflowDebug = ref(false)

// Load page data
const automationApplicationType = $registry.get(
  'application',
  AutomationApplicationType.getType()
)

const { data: pageData } = await useAsyncData(
  () => `automation-workflow-${automationId.value}-${workflowId.value}`,
  async () => {
    try {
      const automation = await $store.dispatch(
        'application/selectById',
        automationId.value
      )

      const workspace = await $store.dispatch(
        'workspace/selectById',
        automation.workspace.id
      )

      await automationApplicationType.loadExtraData(automation)

      const workflow = await $store.dispatch('automationWorkflow/selectById', {
        automation,
        workflowId: workflowId.value,
      })

      await $store.dispatch('automationHistory/fetchWorkflowHistory', {
        workflowId: workflowId.value,
      })

      await $store.dispatch('automationWorkflowNode/fetch', {
        workflow,
      })

      return {
        automation,
        workspace,
        workflow,
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
const workflow = computed(
  () => $store.getters['automationWorkflow/getSelected']
)

// Computed properties
const isDev = computed(() => import.meta.env.MODE === 'development')

const workflowNodes = computed(() => {
  if (!workflow.value?.nodes) {
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
    if (!workflow.value) {
      return
    }
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
  if (!workflow.value) {
    return
  }
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

const leavingRoute = ref(false)
onBeforeRouteLeave((to, from) => {
  onRouteChange(from)
  leavingRoute.value = true
})

onUnmounted(() => {
  if (leavingRoute.value) {
    $store.dispatch('automationWorkflow/unselect')
  }
})
</script>
