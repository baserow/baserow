<template>
  <div>
    <Toasts></Toasts>
    <div class="public-view__table">
      <Table
        v-if="database && table && view"
        :database="database"
        :table="table"
        :fields="fields"
        :view="view"
        :read-only="true"
        :table-loading="false"
        :store-prefix="'page/'"
      ></Table>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useAsyncData, useNuxtApp } from '#app'
import { useHead } from '#imports'

import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import Table from '@baserow/modules/database/components/table/Table'
import ViewService from '@baserow/modules/database/services/view'
import { PUBLIC_PLACEHOLDER_ENTITY_ID } from '@baserow/modules/database/utils/constants'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { keyboardShortcutsToPriorityEventBus } from '@baserow/modules/core/utils/events'

definePageMeta({
  middleware: ['settings'],
})

const route = useRoute()
const nuxtApp = useNuxtApp()
const { $store, $realtime, $priorityBus, $config, $i18n } = nuxtApp

const originalLanguageBeforeDetect = ref(null)
originalLanguageBeforeDetect.value = $i18n.locale
$i18n.locale = $i18n.getBrowserLocale()

const { data, error } = await useAsyncData(
  `database-public-view-${route.params.slug}`,
  async () => {
    const nuxt = useNuxtApp()
    const { $store, $client, $registry, runWithContext } = nuxt
    const slug = route.params.slug

    const publicAuthToken = await $store.dispatch(
      'page/view/public/setAuthTokenFromCookiesIfNotSet',
      { slug }
    )

    try {
      await $store.dispatch('page/view/public/setIsPublic', true)

      const { data } = await ViewService($client).fetchPublicViewInfo(
        slug,
        publicAuthToken
      )

      const { applications } = await runWithContext(() =>
        $store.dispatch('application/forceSetAll', {
          applications: [
            {
              id: PUBLIC_PLACEHOLDER_ENTITY_ID,
              type: DatabaseApplicationType.getType(),
              tables: [{ id: PUBLIC_PLACEHOLDER_ENTITY_ID }],
              workspace: { id: PUBLIC_PLACEHOLDER_ENTITY_ID },
            },
          ],
        })
      )

      const database = applications[0]
      const table = database.tables[0]
      await runWithContext(() =>
        $store.dispatch('application/select', database)
      )
      await runWithContext(() =>
        $store.dispatch('table/forceSelect', { database, table })
      )

      const { fields } = await runWithContext(() =>
        $store.dispatch('field/forceSetFields', {
          fields: data.fields,
        })
      )

      // We must manually set the filters disabled because it should always be false in
      // this case and it's not provided by the backend.
      data.view.filters_disabled = false
      data.view.filter_type = 'AND'
      const { view } = await runWithContext(() =>
        $store.dispatch('view/forceCreate', {
          data: data.view,
        })
      )

      await runWithContext(() => $store.dispatch('view/select', view))

      // It might be possible that the view also has some stores that need to be
      // filled with initial data, so we're going to call the fetch function here.
      const type = $registry.get('view', view.type)
      await runWithContext(() =>
        type.fetch(
          { store: $store, app: nuxt },
          database,
          view,
          fields,
          'page/'
        )
      )

      return { success: true, database, table }
    } catch (e) {
      const statusCode = e.response?.status
      // password protected view requires authentication
      if (statusCode === 401) {
        return {
          redirect: {
            name: 'database-public-view-auth',
            params: { slug },
            query: { original: route.path },
          },
        }
      } else if (statusCode === 404) {
        throw createError({ statusCode: 404, message: 'View not found.' })
      } else {
        throw createError({
          statusCode: 500,
          message: e.message || 'Error loading view.',
        })
      }
    }
  }
)

if (error.value) {
  if (error.value.statusCode === 404) {
    showError(error.value)
  } else {
    throw error.value
  }
}

if (data.value?.redirect) {
  await navigateTo(data.value.redirect)
}

const database = computed(() => data.value?.database)
const table = computed(() => data.value?.table)
const fields = computed(() => $store.getters['field/getAll'])
const view = computed(() => $store.getters['view/getSelected'])

useHead(() => {
  const head = { title: view.value?.name || 'View' }
  if (view.value && !view.value.show_logo) {
    head.titleTemplate = '%s'
  }
  return head
})

let keydownEvent = null

function keyDown(event) {
  keyboardShortcutsToPriorityEventBus(event, $priorityBus)
}

onMounted(() => {
  keydownEvent = (event) => keyDown(event)
  document.body.addEventListener('keydown', keydownEvent)

  if (!$config.public.disableAnonymousPublicViewWsConnections) {
    $realtime.connect(true, true)

    const token = $store.getters['page/view/public/getAuthToken']
    $realtime.subscribe('view', { slug: route.params.slug, token })
  }
})

onBeforeUnmount(() => {
  $i18n.locale = originalLanguageBeforeDetect.value

  document.body.removeEventListener('keydown', keydownEvent)

  if (!$config.public.disableAnonymousPublicViewWsConnections) {
    $realtime.subscribe(null)
    $realtime.disconnect()
  }
})
</script>
