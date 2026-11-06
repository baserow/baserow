<template>
  <div class="data-source-test-form">
    <Button
      :loading="isLoading"
      :disabled="isLoading"
      class="data-source-test-form__button"
      type="secondary"
      @click="testDataSource()"
    >
      {{ buttonLabel }}
    </Button>

    <SampleDataViewer
      v-if="testError"
      :sample-data="testError"
      is-error
      :modal-title="sampleDataModalTitle"
      :modal-subtitle="$t('dataSourceTestForm.sampleDataModalSubTitle')"
    />
    <SampleDataViewer
      v-else-if="hasSampleData"
      :sample-data="sampleData"
      :modal-title="sampleDataModalTitle"
      :modal-subtitle="$t('dataSourceTestForm.sampleDataModalSubTitle')"
    />
    <Alert v-else type="info-neutral" class="margin-bottom-0">
      <p>{{ $t('dataSourceTestForm.testDescription') }}</p>
    </Alert>
  </div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { useStore } from 'vuex'
import SampleDataViewer from '@baserow/modules/core/components/SampleDataViewer'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

const { $i18n, $registry } = useNuxtApp()
const store = useStore()

const applicationContext = inject('applicationContext')

const props = defineProps({
  dataSource: {
    type: Object,
    required: true,
  },
  page: {
    type: Object,
    required: true,
  },
})

const isLoading = ref(false)

// The error of the last test. The data source keeps the sample data of its
// last successful test, so the error is only known from the response.
const testError = ref(null)

const serviceType = computed(() =>
  $registry.get('service', props.dataSource.type)
)

const sample = computed(() => serviceType.value.getSampleData(props.dataSource))

const hasSampleData = computed(() =>
  Boolean(sample.value && !sample.value._error)
)

const sampleData = computed(() => {
  if (serviceType.value.returnsList && sample.value?.data) {
    return sample.value.data.results
  }
  return sample.value?.data
})

const sampleDataModalTitle = computed(() =>
  $i18n.t('dataSourceTestForm.sampleDataModalTitle', {
    dataSourceName: props.dataSource.name,
  })
)

const buttonLabel = computed(() =>
  hasSampleData.value
    ? $i18n.t('dataSourceTestForm.buttonLabelTestAgain')
    : $i18n.t('dataSourceTestForm.buttonLabelTest')
)

const testDataSource = async () => {
  isLoading.value = true
  testError.value = null

  const dispatchContext = DataProviderType.getAllDataSourceDispatchContext(
    $registry.getAll('builderDataProvider'),
    { ...applicationContext, page: props.page }
  )

  try {
    await store.dispatch('dataSource/simulateDispatch', {
      page: props.page,
      dataSourceId: props.dataSource.id,
      dispatchContext,
    })
  } catch (error) {
    testError.value =
      error.response?.data?.detail ||
      $i18n.t('dataSourceTestForm.unexpectedError')
  } finally {
    isLoading.value = false
  }
}
</script>
