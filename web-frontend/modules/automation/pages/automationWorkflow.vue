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
import { normalizeError } from '@baserow/modules/database/utils/errors'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'selectWorkspaceAutomationWorkflow',
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

// Load page data
const automationApplicationType = $registry.get(
  'application',
  AutomationApplicationType.getType()
)

const { data: pageData, error } = await useAsyncData(
  () =>
    `automation-workflow-${route.params.automationId}-${route.params.workflowId}`,
  async () => {
    try {
      const automation = $store.getters['application/getSelected']
      const workspace = $store.getters['workspace/getSelected']
      const workflow = $store.getters['automationWorkflow/getSelected']

      await automationApplicationType.loadExtraData(automation)

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
      if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
        throw e
      }

      const statusCode = e.response?.status || 500

      throw createError({
        statusCode,
        message:
          statusCode === 404
            ? 'Automation workflow not found.'
            : normalizeError(e).message,
        data: {
          report: statusCode >= 500,
        },
        fatal: true,
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
