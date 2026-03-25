<template>
  <div v-if="dashboard" class="dashboard-app">
    <DashboardHeader :dashboard="dashboard" />
    <DashboardContent :dashboard="dashboard" />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { useNuxtApp, useAsyncData, createError, useHead } from '#app'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'
import DashboardContent from '@baserow/modules/dashboard/components/DashboardContent'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'dashboardLoading',
  ],
})

const store = useStore()
const route = useRoute()
const { $hasPermission, $realtime } = useNuxtApp()

const {
  data,
  pending,
  error: fetchError,
} = await useAsyncData(
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

if (fetchError.value) {
  throw fetchError.value
}

const dashboard = computed(() => data.value?.dashboard)

useHead(() => ({
  title: dashboard.value?.name || '',
}))

// Mounted logic
onMounted(() => {
  if (dashboard.value) {
    $realtime.subscribe('dashboard', { dashboard_id: dashboard.value.id })
  }
})

// Cleanup
onBeforeUnmount(() => {
  if (dashboard.value) {
    $realtime.unsubscribe('dashboard', { dashboard_id: dashboard.value.id })
  }
})
</script>
