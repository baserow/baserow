<template>
  <DashboardSkeleton v-if="!ready" />
  <div v-else-if="dashboard" class="dashboard-app">
    <DashboardHeader :dashboard="dashboard" />
    <DashboardContent :dashboard="dashboard" />
  </div>
</template>

<script setup>
import { computed, watch, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { useNuxtApp, createError, useHead } from '#app'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'
import DashboardSkeleton from '@baserow/modules/dashboard/components/DashboardSkeleton'
import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'
import DashboardContent from '@baserow/modules/dashboard/components/DashboardContent'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'selectWorkspaceDashboard',
  ],
})

const store = useStore()
const route = useRoute()
const { $hasPermission, $realtime } = useNuxtApp()

const { data, ready } = await usePageAsyncData(
  `dashboard-data-${route.params.dashboardId}`,
  async () => {
    try {
      const dashboard = store.getters['application/getSelected']
      const workspace = store.getters['workspace/getSelected']

      const forEditing = $hasPermission(
        'application.update',
        dashboard,
        workspace.id
      )

      await store.dispatch('dashboardApplication/fetchInitial', {
        dashboardId: dashboard.id,
        forEditing,
      })

      return {
        workspace,
        dashboard,
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
            ? 'Dashboard not found.'
            : normalizeError(e).message,
        data: {
          report: statusCode >= 500,
        },
        fatal: true,
      })
    }
  }
)

const dashboard = computed(() => data.value?.dashboard)

useHead(() => ({
  title: dashboard.value?.name || '',
}))

/**
 * Subscribe to the realtime updates of the dashboard as soon as the async data
 * is ready. This can't happen in the onMounted hook because the page is mounted
 * before the async data has been fetched on client-side navigation.
 */
let subscribedDashboardId = null
watch(
  ready,
  (isReady) => {
    if (isReady && subscribedDashboardId === null && dashboard.value) {
      subscribedDashboardId = dashboard.value.id
      $realtime.subscribe('dashboard', { dashboard_id: subscribedDashboardId })
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (subscribedDashboardId !== null) {
    $realtime.unsubscribe('dashboard', { dashboard_id: subscribedDashboardId })
    subscribedDashboardId = null
  }
})
</script>
