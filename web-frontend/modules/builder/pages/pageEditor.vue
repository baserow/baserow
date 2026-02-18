<template>
  <PageEditorContent
    v-if="!pending"
    :workspace="workspace"
    :builder="builder"
    :page="currentPage"
  />
</template>

<script setup>
import { useHead, useAsyncData } from '#imports'
import { computed } from 'vue'
import { onBeforeRouteUpdate, onBeforeRouteLeave } from 'vue-router'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
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

// Load page data
const {
  data: pageData,
  error: pageError,
  pending,
} = await useAsyncData(
  () => `page-editor-${route.params.builderId}-${route.params.pageId}`,
  async () => {
    // The objects are selected by the middleware
    const loadedBuilder = $store.getters['application/getSelected']
    const loadedWorkspace = $store.getters['workspace/getSelected']
    const page = $store.getters['page/getSelected']

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

      const sharedPage =
        await $store.getters['page/getSharedPage'](loadedBuilder)

      return {
        workspace: loadedWorkspace,
        builder: loadedBuilder,
        page,
        sharedPage,
      }
    } catch (e) {
      if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
        throw e
      }

      throw createError({
        statusCode: 404,
        message: $i18n.t('pageEditor.pageNotFound'),
      })
    }
  }
)

if (pageError.value) {
  // If we have an error we want to display it.
  if (pageError.value.statusCode === 404) {
    showError(pageError.value)
  } else {
    throw pageError.value
  }
}

const workspace = computed(() => pageData.value.workspace)
const builder = computed(() => pageData.value.builder)
const currentPage = computed(() => pageData.value.page)

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
