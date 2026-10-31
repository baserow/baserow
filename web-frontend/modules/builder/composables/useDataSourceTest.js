import { computed, reactive, ref, unref } from 'vue'
import { useStore } from 'vuex'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

/**
 * The state of testing a data source: dispatching it to fill its sample data.
 * One instance is shared by everything showing the test of a data source,
 * like a Test button in the service form and the result below it.
 *
 * @param {Object} options
 * @param {Function} options.dataSource Returns the data source to test.
 * @param {Function} options.page Returns the page of the data source.
 * @param {Function} options.applicationContext Returns the application
 *   context the dispatch context is built from.
 * @param {Function} [options.beforeTest] Called before the test, to save what
 *   the form changed: the test dispatches the saved data source. Resolves to
 *   false when the test must not run, like when the form isn't valid.
 */
export function useDataSourceTest({
  dataSource,
  page,
  applicationContext,
  beforeTest = null,
}) {
  const { $i18n, $registry } = useNuxtApp()
  const store = useStore()

  const isLoading = ref(false)
  // The error of the last test. The data source keeps the sample data of its
  // last successful test, so the error is only known from the response.
  const error = ref(null)

  const serviceType = computed(() =>
    $registry.get('service', dataSource().type)
  )

  const sample = computed(() => serviceType.value.getSampleData(dataSource()))

  const hasSampleData = computed(() =>
    Boolean(sample.value && !sample.value._error)
  )

  const sampleData = computed(() => {
    if (serviceType.value.returnsList(dataSource()) && sample.value?.data) {
      return sample.value.data.results
    }
    return sample.value?.data
  })

  const test = async () => {
    isLoading.value = true
    error.value = null

    const dispatchContext = DataProviderType.getAllDataSourceDispatchContext(
      $registry.getAll('builderDataProvider'),
      { ...unref(applicationContext()), page: page() }
    )

    try {
      if (beforeTest && (await beforeTest()) === false) {
        return
      }
      await store.dispatch('dataSource/simulateDispatch', {
        page: page(),
        dataSourceId: dataSource().id,
        dispatchContext,
      })
    } catch (err) {
      error.value =
        err.response?.data?.detail ||
        $i18n.t('dataSourceTestForm.unexpectedError')
    } finally {
      isLoading.value = false
    }
  }

  return reactive({
    isLoading,
    error,
    hasSampleData,
    sampleData,
    test,
  })
}
