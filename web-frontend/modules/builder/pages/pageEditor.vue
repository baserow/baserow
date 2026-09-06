<template>
  <PageEditorContent
    :workspace="workspace"
    :builder="builder"
    :page="currentPage"
    :loading="loading"
  />
</template>

<script setup>
import { useHead } from '#imports'
import { usePageAsyncData } from '@baserow/modules/core/composables/usePageAsyncData'
import { ref } from 'vue'
import { onBeforeRouteUpdate, onBeforeRouteLeave } from 'vue-router'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'
import _ from 'lodash'
import PageEditorContent from '@baserow/modules/builder/components/PageEditorContent.vue'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'selectWorkspaceBuilderPage',
    'pendingJobs',
  ],
})

const mode = 'editing'
const route = useRoute()
const { t } = useI18n()
const { $store, $registry, $i18n } = useNuxtApp()

useHead(() => ({
  title: t('pageEditor.title'),
}))

// The workspace, builder and page are selected by the `selectWorkspaceBuilderPage`
// middleware, so they're there when the page renders. The elements, data sources
// and workflow actions are fetched afterwards. They're read once instead of being
// computed, because leaving the page unselects them while this page is still
// rendered.
const workspace = ref($store.getters['workspace/getSelected'])
const builder = ref($store.getters['application/getSelected'])
const currentPage = ref($store.getters['page/getSelected'])

const { loading } = await usePageAsyncData(
  () => `page-editor-${route.params.builderId}-${route.params.pageId}`,
  async () => {
    const loadedBuilder = builder.value
    const page = currentPage.value

    try {
      $store.dispatch('userSourceUser/setCurrentApplication', {
        application: loadedBuilder,
      })

      const builderApplicationType = $registry.get(
        'application',
        BuilderApplicationType.getType()
      )

      if (page.shared) {
        throw createError({
          statusCode: 404,
          message: $i18n.t('pageEditor.pageNotFound'),
          data: {
            report: false,
          },
          fatal: true,
        })
      }

      await builderApplicationType.loadExtraData(loadedBuilder, mode)

      await Promise.all([
        $store.dispatch('dataSource/fetch', { page }),
        $store.dispatch('element/fetch', { builder: loadedBuilder, page }),
        $store.dispatch('builderWorkflowAction/fetch', { page }),
      ])

      await DataProviderType.initAll($registry.getAll('builderDataProvider'), {
        builder: loadedBuilder,
        page,
        mode,
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
            ? $i18n.t('pageEditor.pageNotFound')
            : normalizeError(e).message,
        data: {
          report: statusCode >= 500,
        },
        fatal: true,
      })
    }
  }
)

// Navigation guards
onBeforeRouteUpdate((to, from) => {
  // Unselect previously selected element
  const currentBuilder = $store.getters['application/get'](
    parseInt(from.params.builderId)
  )
  if (currentBuilder) {
    $store.dispatch('element/select', {
      builder: currentBuilder,
      element: null,
    })
  }
  if (from.params.builderId !== to.params?.builderId) {
    // When we switch from one application to another we want to logoff the current user
    if (currentBuilder) {
      // We want to reload once only data for this builder next time
      $store.dispatch('application/forceUpdate', {
        application: currentBuilder,
        data: { _loadedOnce: false },
      })
      $store.dispatch('userSourceUser/logoff', {
        application: currentBuilder,
      })
    }
  }
})

onBeforeRouteLeave((to, from) => {
  $store.dispatch('page/unselect')

  const builderToLeave = $store.getters['application/get'](
    parseInt(from.params.builderId)
  )

  if (builderToLeave) {
    // Unselect previously selected element
    $store.dispatch('element/select', {
      builder: builderToLeave,
      element: null,
    })
    // We want to reload once only data for this builder next time
    $store.dispatch('application/forceUpdate', {
      application: builderToLeave,
      data: { _loadedOnce: false },
    })
    $store.dispatch('userSourceUser/logoff', { application: builderToLeave })
  }
})
</script>
