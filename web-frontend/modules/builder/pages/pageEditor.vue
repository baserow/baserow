<template>
  <!-- TODO MIG add a skeleton loader while the page is loading. -->
  <div v-if="builder && currentPage && sharedPage" class="page-editor">
    <PageHeader />
    <div class="layout__col-2-2 page-editor__content">
      <div :style="{ width: `calc(100% - ${panelWidth}px)` }">
        <PagePreview />
      </div>
      <div
        class="page-editor__side-panel"
        :style="{ width: `${panelWidth}px` }"
      >
        <PageSidePanels />
      </div>
    </div>
  </div>
</template>

<script setup>
import { useHead, useAsyncData } from '#imports'
import { ref, computed, watch, provide } from 'vue'
import { onBeforeRouteUpdate, onBeforeRouteLeave } from 'vue-router'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import PageHeader from '@baserow/modules/builder/components/page/header/PageHeader'
import PagePreview from '@baserow/modules/builder/components/page/PagePreview'
import PageSidePanels from '@baserow/modules/builder/components/page/PageSidePanels'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput'
import _ from 'lodash'

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

const panelWidth = ref(360)

// Provide values for child components
const applicationContext = computed(() => ({
  workspace: workspace.value,
  builder: builder.value,
  mode,
}))

useHead(() => ({
  title: t('pageEditor.title'),
}))

// Load page data
const {
  data: pageData,
  error: pageError,
  pending: pagePending,
  refresh: refreshPage,
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

      return {
        workspace: loadedWorkspace,
        builder: loadedBuilder,
        page,
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

const workspace = computed(() => pageData.value?.workspace ?? null)
const builder = computed(() => pageData.value?.builder ?? null)
const currentPage = computed(() => pageData.value?.page ?? null)

// Computed properties
const dataSources = computed(() => {
  return $store.getters['dataSource/getPageDataSources'](currentPage.value)
})

const sharedPage = computed(() => {
  if (!builder.value) return null
  return $store.getters['page/getSharedPage'](builder.value)
})

const sharedDataSources = computed(() => {
  return $store.getters['dataSource/getPageDataSources'](sharedPage.value)
})

const dispatchContext = computed(() => {
  if (!currentPage.value || !applicationContext.value) return {}
  return DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { ...applicationContext.value, page: currentPage.value }
  )
})

const applicationDispatchContext = computed(() => {
  if (!builder.value) return {}
  return DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { builder: builder.value, mode }
  )
})

provide('workspace', workspace)
provide('builder', builder)
provide('currentPage', currentPage)
provide('mode', mode)
provide('formulaComponent', ApplicationBuilderFormulaInput)
provide('applicationContext', applicationContext)

// Watchers
watch(
  dataSources,
  () => {
    $store.dispatch('dataSourceContent/debouncedFetchPageDataSourceContent', {
      page: currentPage.value,
      data: dispatchContext.value,
      mode,
    })
  },
  { deep: true }
)

watch(
  sharedDataSources,
  () => {
    $store.dispatch('dataSourceContent/debouncedFetchPageDataSourceContent', {
      page: sharedPage.value,
      data: dispatchContext.value,
    })
  },
  { deep: true }
)

watch(
  dispatchContext,
  (newDispatchContext, oldDispatchContext) => {
    if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
      $store.dispatch('dataSourceContent/debouncedFetchPageDataSourceContent', {
        page: currentPage.value,
        data: newDispatchContext,
        mode,
      })
    }
  },
  { deep: true }
)

watch(
  applicationDispatchContext,
  (newDispatchContext, oldDispatchContext) => {
    if (!_.isEqual(newDispatchContext, oldDispatchContext)) {
      $store.dispatch('dataSourceContent/debouncedFetchPageDataSourceContent', {
        page: sharedPage.value,
        data: newDispatchContext,
      })
    }
  },
  { deep: true }
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
