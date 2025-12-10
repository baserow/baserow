<template>
  <div class="page-editor">
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
    'pendingJobs',
  ],
})

const mode = 'editing'
const route = useRoute()
const router = useRouter()
const { $store, $registry, $i18n } = useNuxtApp()

const panelWidth = ref(360)
const workspace = ref(null)
const builder = ref(null)
const currentPage = ref(null)

// Provide values for child components
const applicationContext = computed(() => ({
  workspace: workspace.value,
  builder: builder.value,
  mode,
}))

provide('workspace', workspace)
provide('builder', builder)
provide('currentPage', currentPage)
provide('mode', mode)
provide('formulaComponent', ApplicationBuilderFormulaInput)
provide('applicationContext', applicationContext)

console.log('page setup invoked')

// Load page data
const { error: pageError } = await useAsyncData(
  `page-editor-${route.params.builderId}-${route.params.pageId}`,
  async () => {
    const builderId = parseInt(route.params.builderId)
    const pageId = parseInt(route.params.pageId)

    try {
      console.log('dispatch starts')
      const loadedBuilder = await $store.dispatch(
        'application/selectById',
        builderId
      )
      $store.dispatch('userSourceUser/setCurrentApplication', {
        application: loadedBuilder,
      })
      const loadedWorkspace = await $store.dispatch(
        'workspace/selectById',
        loadedBuilder.workspace.id
      )
      console.log('continue')

      const builderApplicationType = $registry.get(
        'application',
        BuilderApplicationType.getType()
      )

      // Select the page first - this will validate it exists
      const page = await $store.dispatch('page/selectById', {
        builder: loadedBuilder,
        pageId,
      })
      console.log('after')

      // Shared pages cannot be edited
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

      console.log('found page', page)

      workspace.value = loadedWorkspace
      builder.value = loadedBuilder
      currentPage.value = page

      return { success: true }
    } catch (e) {
      console.log('error', e)
      // In case of a network error we want to fail hard.
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

// Computed properties
const dataSources = computed(() => {
  if (!currentPage.value) return []
  return $store.getters['dataSource/getPageDataSources'](currentPage.value)
})

const sharedPage = computed(() => {
  if (!builder.value) return null
  return $store.getters['page/getSharedPage'](builder.value)
})

const sharedDataSources = computed(() => {
  if (!sharedPage.value) return []
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
  $store.dispatch('element/select', {
    builder: currentBuilder,
    element: null,
  })
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
