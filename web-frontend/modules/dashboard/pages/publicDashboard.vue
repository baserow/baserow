<template>
  <div>
    <Toasts></Toasts>
    <PublicDashboard
      v-if="dashboard"
      :dashboard="dashboard"
      :loading="loading"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  createError,
  navigateTo,
  useAsyncData,
  useNuxtApp,
  useState,
} from '#app'
import { useHead } from '#imports'

import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import PublicDashboard from '@baserow/modules/dashboard/components/PublicDashboard'
import PublicDashboardService from '@baserow/modules/dashboard/services/publicDashboard'
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'
import { PUBLIC_PLACEHOLDER_ENTITY_ID } from '@baserow/modules/database/utils/constants'

definePageMeta({
  middleware: ['settings'],
})

const route = useRoute()
const { $store, $i18n } = useNuxtApp()
const slug = route.params.slug

// Visitors see the dashboard in the language of their browser, like public views.
const originalLocale = ref($i18n.locale.value)
const detectedLocale = useState('public-dashboard-detected-locale', () => {
  return $i18n.getBrowserLocale() || $i18n.defaultLocale
})
$i18n.locale.value = detectedLocale.value
await $i18n.loadLocaleMessages(detectedLocale.value)

// A password protected dashboard hands out a token for the right password,
// which the password page keeps in a cookie keyed by the slug. It is read here,
// on the server and in the browser, so that every request can carry it.
const authToken = await $store.dispatch(
  'dashboardApplication/restorePublicAuthToken',
  { slug }
)

const { data, error } = await useAsyncData(
  `dashboard-public-${slug}`,
  async () => {
    const { $client } = useNuxtApp()

    try {
      const { data } = await PublicDashboardService($client).fetchInfo(
        slug,
        authToken
      )
      return data
    } catch (e) {
      const statusCode = e.response?.status

      if (statusCode === 401) {
        // The password page stores the token and sends the visitor back here.
        return {
          redirect: {
            name: 'dashboard-public-auth',
            params: { slug },
            query: { original: route.path },
          },
        }
      } else if (statusCode === 404) {
        throw createError({
          statusCode: 404,
          message: 'Dashboard not found.',
          data: {
            report: false,
          },
          fatal: true,
        })
      }

      throw createError({
        statusCode: statusCode || 500,
        message: e.message || 'Error loading dashboard.',
        fatal: true,
      })
    }
  }
)

if (error.value) {
  throw error.value
}

// The components look up permissions through the workspace of the dashboard.
// Visitors have none, so a placeholder workspace hides every edit affordance.
const dashboard = computed(() => {
  const publicDashboard = data.value?.dashboard
  if (!publicDashboard) {
    return null
  }
  return {
    ...publicDashboard,
    type: DashboardApplicationType.getType(),
    workspace: { id: PUBLIC_PLACEHOLDER_ENTITY_ID },
  }
})

const redirect = data.value?.redirect
if (redirect) {
  await navigateTo(redirect)
} else {
  // The widgets and data sources arrive with the dashboard, so the store only
  // has to be filled. This runs during server side rendering and again while
  // hydrating, which is harmless because nothing has been dispatched yet.
  await $store.dispatch('dashboardApplication/openPublicDashboard', {
    slug,
    authToken,
    dashboardId: data.value.dashboard.id,
    widgets: data.value.widgets,
    dataSources: data.value.data_sources,
  })
}

const loading = computed(() => $store.getters['dashboardApplication/isLoading'])

useHead(() => {
  const head = { title: dashboard.value?.name || 'Dashboard' }
  if (dashboard.value && !dashboard.value.show_logo) {
    head.titleTemplate = '%s'
  }
  return head
})

onMounted(() => {
  if (redirect) {
    return
  }
  // The data is loaded in the browser only. The server rendered page already
  // shows the widgets in their loading state.
  $store.dispatch('dashboardApplication/dispatchDataSources')
})

onBeforeUnmount(() => {
  $i18n.locale.value = originalLocale.value
})
</script>
