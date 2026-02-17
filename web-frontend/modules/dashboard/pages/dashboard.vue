<template>
  <div class="dashboard-app">
    <DashboardHeader :dashboard="dashboard" />
    <DashboardContent :dashboard="dashboard" />
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useNuxtApp, useAsyncData, createError, useHead } from '#app'

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
    const dashboard = store.getters['application/getSelected']
    const workspace = store.getters['workspace/getSelected']
    return {
      workspace,
      dashboard,
    }
  }
)

if (fetchError.value) {
  throw fetchError.value
}

const dashboard = computed(() => data.value?.dashboard)
const workspace = computed(() => data.value?.workspace)

useHead(() => ({
  title: dashboard.value?.name || '',
}))

// Mounted logic
onMounted(() => {
  const forEditing = $hasPermission(
    'application.update',
    dashboard.value,
    workspace.value.id
  )

  store.dispatch('dashboardApplication/fetchInitial', {
    dashboardId: dashboard.value.id,
    forEditing,
  })

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
