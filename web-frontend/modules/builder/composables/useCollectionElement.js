import { ref, computed, watch, unref } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { handleDispatchError } from '@baserow/modules/builder/utils/error'
import _ from 'lodash'
import { useElement } from './useElement'

export function useCollectionElement(props) {
  const store = useStore()
  const nuxtApp = useNuxtApp()

  const allElement = useElement(props)

  const {
    element,
    builder,
    workspace,
    elementPage,
    currentPage,
    applicationContext,
    elementType,
  } = allElement

  // =========
  // state
  // =========
  const adhocFilters = ref()
  const adhocSortings = ref()
  const adhocSearch = ref()
  const currentOffset = ref(0)
  const errorNotified = ref(false)
  const resetTimeout = ref(null)
  const contentFetchEnabled = ref(true)

  const reset = computed(() =>
    store.getters['elementContent/getReset'](unref(element))
  )

  const sharedPage = computed(() =>
    store.getters['page/getSharedPage'](unref(builder))
  )

  const dataSource = computed(() => {
    const el = unref(element)
    if (!el.data_source_id) {
      return null
    }
    const pages = [unref(currentPage), sharedPage.value]
    return store.getters['dataSource/getPagesDataSourceById'](
      pages,
      el.data_source_id
    )
  })

  const dataSourceType = computed(() => {
    if (!dataSource.value) {
      return null
    }
    return nuxtApp.$registry.get('service', dataSource.value.type)
  })

  const dataSourceInError = computed(() => {
    const type = unref(elementType)
    const el = unref(element)
    return !!type.getDataSourceErrorMessage({
      workspace: unref(workspace),
      page: unref(elementPage),
      element: el,
      builder: unref(builder),
    })
  })

  const elementContent = computed(() => {
    const content = unref(elementType).getElementCurrentContent(
      unref(applicationContext)
    )
    return Array.isArray(content) ? content : []
  })

  const hasMorePage = computed(() =>
    store.getters['elementContent/getHasMorePage'](unref(element))
  )

  const elementIsInError = computed(() =>
    unref(elementType).isInError(unref(element), unref(applicationContext))
  )

  const contentLoading = computed(() => {
    const loading = store.getters['elementContent/getLoading'](unref(element))
    return loading && !elementIsInError.value
  })

  const dispatchContext = computed(() =>
    DataProviderType.getAllDataSourceDispatchContext(
      nuxtApp.$registry.getAll('builderDataProvider'),
      unref(applicationContext)
    )
  )

  const elementHasSourceOfData = computed(() =>
    unref(elementType).hasSourceOfData(unref(element))
  )

  const adhocRefinements = computed(() => ({
    filters: adhocFilters.value,
    sortings: adhocSortings.value,
    search: adhocSearch.value,
  }))

  // not in original computed, but if you want it:
  const elementAncestors = computed(() =>
    store.getters['element/getAncestors'](unref(element))
  )

  const fetchElementContent = (payload) =>
    store.dispatch('elementContent/fetchElementContent', payload)

  const clearElementContent = (payload) =>
    store.dispatch('elementContent/clearElementContent', payload)

  const canFetch = () => {
    return !dataSourceInError.value && contentFetchEnabled.value
  }

  /** Override this if you want to handle content fetch errors */
  const onContentFetchError = (error) => {
    // If the request failed without reaching the server, `error.response`
    // will be `undefined`, so we need to check that before checking the
    // HTTP status code
    if (error.response && [400, 404].includes(error.response.status)) {
      contentFetchEnabled.value = false
    }
  }

  const fetchContent = async (range, replace) => {
    if (!canFetch()) {
      return
    }

    const el = unref(element)
    const ctx = unref(applicationContext)

    try {
      await fetchElementContent({
        page: unref(elementPage),
        element: el,
        dataSource: dataSource.value,
        data: dispatchContext.value,
        range,
        filters: adhocRefinements.value.filters,
        sortings: adhocRefinements.value.sortings,
        search: adhocRefinements.value.search,
        mode: ctx.mode,
        replace,
      })

      currentOffset.value = range[0] + el.items_per_page
    } catch (error) {
      // Handle the HTTP error if needed
      onContentFetchError(error)

      // We need to only launch one toast error message per element,
      // not one per element fetch, or we can end up with many error
      // toasts per element sharing a datasource.
      if (!errorNotified.value) {
        errorNotified.value = true
        const dsName = dataSource.value?.name
        const t = nuxtApp.$i18n.t

        handleDispatchError(
          error,
          nuxtApp,
          nuxtApp.$i18n.t('builderToast.errorDataSourceDispatch', {
            name: dsName,
          })
        )
      }
    }
  }

  const loadMore = async (replace = false) => {
    await fetchContent(
      [currentOffset.value, unref(element).items_per_page],
      replace
    )
  }

  const debouncedReset = () => {
    clearTimeout(resetTimeout.value)
    resetTimeout.value = setTimeout(() => {
      contentFetchEnabled.value = true
      errorNotified.value = false
      currentOffset.value = 0
      loadMore(true)
    }, 500)
  }

  const getPerRecordApplicationContextAddition = ({
    applicationContext,
    row,
    rowIndex,
    field = null,
    ...rest
  }) => {
    const baseContext = applicationContext || unref(applicationContext)

    const newApplicationContext = {
      ...baseContext,
      recordIndexPath: [...baseContext.recordIndexPath, rowIndex],
      ...rest,
    }
    if (field) {
      newApplicationContext.field = field
    }
    if (unref(element).data_source_id) {
      newApplicationContext.recordId = row.__recordId__
    }
    return newApplicationContext
  }

  watch(reset, () => {
    debouncedReset()
  })

  watch(
    () => unref(element).schema_property,
    async (newValue, oldValue) => {
      await clearElementContent({ element: unref(element) })
      if (newValue) {
        debouncedReset()
      }
    }
  )

  watch(
    () => unref(element).data_source_id,
    async () => {
      await clearElementContent({ element: unref(element) })
      debouncedReset()
    }
  )

  watch(
    () => unref(element).items_per_page,
    () => {
      debouncedReset()
    }
  )

  watch(
    dispatchContext,
    (newValue, prevValue) => {
      if (!_.isEqual(newValue, prevValue)) {
        debouncedReset()
      }
    },
    { deep: true }
  )

  watch(adhocRefinements, (newValue, prevValue) => {
    if (!_.isEqual(newValue, prevValue)) {
      debouncedReset()
    }
  })

  useAsyncData(
    () => `element-content-${unref(element).id}`,
    async () => {
      const elType = unref(elementType)
      const el = unref(element)

      if (elType.fetchAtLoad) {
        await fetchContent([0, el.items_per_page], false)
      }

      return {}
    }
  )

  return {
    ...allElement,
    // state
    adhocFilters,
    adhocSortings,
    adhocSearch,
    currentOffset,
    errorNotified,
    resetTimeout,
    contentFetchEnabled,

    // computed
    reset,
    sharedPage,
    dataSource,
    dataSourceType,
    dataSourceInError,
    elementContent,
    hasMorePage,
    contentLoading,
    dispatchContext,
    elementHasSourceOfData,
    adhocRefinements,
    elementIsInError,
    elementAncestors,

    // actions
    fetchElementContent,
    clearElementContent,

    // methods
    debouncedReset,
    fetchContent,
    loadMore,
    canFetch,
    onContentFetchError,
    getPerRecordApplicationContextAddition,
  }
}
