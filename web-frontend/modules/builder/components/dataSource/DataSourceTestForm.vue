<template>
  <div class="data-source-test-form">
    <Button
      v-if="showButton"
      :loading="tester.isLoading"
      :disabled="tester.isLoading"
      class="data-source-test-form__button"
      type="secondary"
      @click="tester.test()"
    >
      {{ buttonLabel }}
    </Button>

    <section class="data-source-test-form__result">
      <div class="data-source-test-form__result-header">
        <div class="data-source-test-form__result-title">
          {{ $t('dataSourceTestForm.lastResponse') }}
          <Badge v-if="tester.error" color="red" size="small" rounded indicator>
            {{ $t('dataSourceTestForm.failed') }}
          </Badge>
          <Badge
            v-else-if="tester.hasSampleData"
            color="green"
            size="small"
            rounded
            indicator
          >
            {{ $t('dataSourceTestForm.succeeded') }}
          </Badge>
        </div>
        <ButtonText
          v-if="tester.error || tester.hasSampleData"
          icon="iconoir-expand"
          size="small"
          @click="$refs.sampleDataModal.show()"
        >
          {{ $t('dataSourceTestForm.openInFull') }}
        </ButtonText>
      </div>
      <pre
        v-if="tester.error"
        class="data-source-test-form__code data-source-test-form__code--error"
        >{{ tester.error }}</pre
      >
      <pre
        v-else-if="tester.hasSampleData"
        class="data-source-test-form__code"
        >{{ formattedSampleData }}</pre
      >
      <p v-else class="data-source-test-form__empty">
        {{ $t('dataSourceTestForm.testDescription') }}
      </p>
    </section>

    <SampleDataModal
      ref="sampleDataModal"
      :sample-data="tester.error || tester.sampleData"
      :title="sampleDataModalTitle"
      :subtitle="$t('dataSourceTestForm.sampleDataModalSubTitle')"
    />
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import SampleDataModal from '@baserow/modules/core/components/SampleDataModal'
import { useDataSourceTest } from '@baserow/modules/builder/composables/useDataSourceTest'

// A long answer is cut short here, the modal shows all of it.
const MAX_FORMATTED_LENGTH = 10000

const { $i18n } = useNuxtApp()

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
  /**
   * Called before the test, to save what the form changed: the test
   * dispatches the saved data source. Resolves to false when the test must
   * not run, like when the form isn't valid.
   */
  beforeTest: {
    type: Function,
    required: false,
    default: null,
  },
  /**
   * Whether to show a Test button. A service form which has a Test button of
   * its own shares the test through `dataSourceTest` and hides this one.
   */
  showButton: {
    type: Boolean,
    required: false,
    default: true,
  },
})

// Shared with the service form when the data source form provides it.
const tester =
  inject('dataSourceTest', null) ??
  useDataSourceTest({
    dataSource: () => props.dataSource,
    page: () => props.page,
    applicationContext: () => applicationContext,
    beforeTest: () => props.beforeTest?.(),
  })

const formattedSampleData = computed(() => {
  const formatted = JSON.stringify(tester.sampleData, null, 2) ?? ''
  return formatted.length > MAX_FORMATTED_LENGTH
    ? `${formatted.slice(0, MAX_FORMATTED_LENGTH)}…`
    : formatted
})

const sampleDataModalTitle = computed(() =>
  $i18n.t('dataSourceTestForm.sampleDataModalTitle', {
    dataSourceName: props.dataSource.name,
  })
)

const buttonLabel = computed(() =>
  tester.hasSampleData
    ? $i18n.t('dataSourceTestForm.buttonLabelTestAgain')
    : $i18n.t('dataSourceTestForm.buttonLabelTest')
)
</script>
