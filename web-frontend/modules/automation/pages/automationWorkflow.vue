<template>
  <AutomationWorkflowContent
    v-if="workspace && automation && workflow"
    :loading="loading"
    :workspace="workspace"
    :automation="automation"
    :workflow="workflow"
  />
</template>

<script setup>
import { ref, computed } from 'vue'
import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'
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

const route = useRoute()
const { $store, $registry } = useNuxtApp()

// The automation, workspace and workflow are selected by the
// `selectWorkspaceAutomationWorkflow` middleware, so they're there when the page
// renders. Only the nodes have to be fetched. They're read once instead of being
// computed, because the next route's middleware selects its own application
// before this page unmounts, and a realtime deletion removes it from the store
// before the redirect away has finished.
const automation = ref($store.getters['application/getSelected'])
const workspace = ref($store.getters['workspace/getSelected'])
const workflow = ref($store.getters['automationWorkflow/getSelected'])

const automationApplicationType = $registry.get(
  'application',
  AutomationApplicationType.getType()
)

const { loading } = await usePageAsyncData(
  () =>
    `automation-workflow-${route.params.automationId}-${route.params.workflowId}`,
  async () => {
    try {
      await automationApplicationType.loadExtraData(automation.value)

      await $store.dispatch('automationWorkflowNode/fetch', {
        workflow: workflow.value,
      })

      return true
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
