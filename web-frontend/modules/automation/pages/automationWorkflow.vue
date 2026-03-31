<template>
  <AutomationWorkflowContent
    v-if="workspace && automation && workflow"
    :loading="workflowLoading"
    :workspace="workspace"
    :automation="automation"
    :workflow="workflow"
  />
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAsyncData } from '#imports'
import { onBeforeRouteUpdate, onBeforeRouteLeave } from 'vue-router'

import AutomationWorkflowContent from '@baserow/modules/automation/components/AutomationWorkflowContent'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'
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

const workflowLoading = ref(false)

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

// Load page data
const automationApplicationType = $registry.get(
  'application',
  AutomationApplicationType.getType()
)

const { data: pageData, error } = await useAsyncData(
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

      workflowLoading.value = false

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

if (error.value) {
  throw error.value
}

// Computed properties from async data
const automation = computed(() => pageData.value?.automation ?? null)
const workspace = computed(() => pageData.value?.workspace ?? null)
const workflow = computed(() => pageData.value?.workflow ?? null)

function onRouteChange(from) {
  const currentAutomation = $store.getters['application/get'](
    parseInt(from.params.automationId)
  )
  if (currentAutomation) {
    try {
      workflowLoading.value = true
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
