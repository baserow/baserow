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
import PageHeader from '@baserow/modules/builder/components/page/header/PageHeader'
import PagePreview from '@baserow/modules/builder/components/page/PagePreview'
import PageSidePanels from '@baserow/modules/builder/components/page/PageSidePanels'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import ApplicationBuilderFormulaInput from '@baserow/modules/builder/components/ApplicationBuilderFormulaInput'
import _ from 'lodash'

const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
  builder: {
    type: Object,
    required: true,
  },
  page: {
    type: Object,
    required: true,
  },
})

const mode = 'editing'
const { $store, $registry } = useNuxtApp()

const panelWidth = ref(360)

const applicationContext = computed(() => ({
  workspace: props.workspace,
  builder: props.builder,
  mode,
}))

const sharedPage = computed(() =>
  $store.getters['page/getSharedPage'](props.builder)
)

const dataSources = computed(() => {
  return $store.getters['dataSource/getPageDataSources'](props.page)
})

const sharedDataSources = computed(() => {
  return $store.getters['dataSource/getPageDataSources'](sharedPage.value)
})

const dispatchContext = computed(() => {
  return DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { ...applicationContext.value, page: props.page }
  )
})

const applicationDispatchContext = computed(() => {
  return DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { builder: props.builder, mode }
  )
})

provide('workspace', props.workspace)
provide('builder', props.builder)
provide('currentPage', props.page)
provide('mode', mode)
provide('formulaComponent', ApplicationBuilderFormulaInput)
provide('applicationContext', applicationContext)

// Watchers
watch(
  dataSources,
  () => {
    $store.dispatch('dataSourceContent/debouncedFetchPageDataSourceContent', {
      page: props.page,
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
        page: props.page,
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
</script>
