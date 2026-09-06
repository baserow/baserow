<template>
  <div class="dashboard-app">
    <DashboardHeader :dashboard="dashboard" :loading="loading" />
    <DashboardContent :dashboard="dashboard" :loading="loading" />
  </div>
</template>

<script setup>
import { computed, watch, onMounted, onBeforeUnmount } from 'vue'
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
    'selectDashboard',
  ],
})

const store = useStore()
const route = useRoute()
const { $hasPermission, $realtime } = useNuxtApp()

// The dashboard is selected by the `selectDashboard` middleware, so it's there
// when the page renders. Only the widgets have to be fetched.
const dashboard = computed(() => store.getters['application/getSelected'])

/**
 * The widgets are fetched without blocking the navigation. While that's running,
 * the page renders a skeleton loading state.
 */
const { status, error: fetchError } = await useAsyncData(
  `dashboard-data-${route.params.dashboardId}`,
  async () => {
    try {
      const workspace = store.getters['workspace/getSelected']
      const forEditing = $hasPermission(
        'application.update',
        dashboard.value,
        workspace.id
      )

      await store.dispatch('dashboardApplication/fetchInitial', {
        dashboardId: dashboard.value.id,
        forEditing,
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
            ? 'Dashboard not found.'
            : normalizeError(e).message,
        data: {
          report: statusCode >= 500,
        },
        fatal: true,
      })
    }
  },
  { lazy: true, server: false }
)

// The store is loading from the moment the widgets are being fetched until they
// have arrived, after which they render with a loading state of their own. The
// `idle` status covers the tick before the fetch has started, because until then
// the widgets of the previously opened dashboard are still in the store.
const widgetsLoading = computed(
  () => store.getters['dashboardApplication/isLoading']
)
const loading = computed(() => status.value === 'idle' || widgetsLoading.value)

// The fetch no longer runs during setup, so an error arrives after the page has
// rendered and has to be shown from here.
watch(
  fetchError,
  (value) => {
    if (value) {
      showError(value)
    }
  },
  { immediate: true }
)

useHead(() => ({
  title: dashboard.value?.name || '',
}))

onMounted(() => {
  if (dashboard.value) {
    $realtime.subscribe('dashboard', { dashboard_id: dashboard.value.id })
  }
})

onBeforeUnmount(() => {
  if (dashboard.value) {
    $realtime.unsubscribe('dashboard', { dashboard_id: dashboard.value.id })
  }
})
</script>
