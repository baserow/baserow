<template>
  <div class="sample-data-viewer">
    <div
      :class="{
        'sample-data-viewer__sample--error': isError,
      }"
    >
      <div class="sample-data-viewer__label">
        {{ viewerLabel }}
      </div>
      <div class="sample-data-viewer__code">
        <pre><code>{{ displayedFormattedSampleData }}</code></pre>
      </div>
    </div>

    <Button
      class="sample-data-viewer__button"
      type="secondary"
      icon="iconoir-code-brackets sample-data-viewer__button-icon"
      @click="showSampleDataModal"
    >
      {{ showViewerLabel }}
    </Button>

    <SampleDataModal
      ref="sampleDataModalRef"
      :sample-data="sampleData"
      :content-type="contentType"
      :sample-data-html="sampleDataHtml"
      :title="modalTitle"
      :subtitle="modalSubtitle"
    />
  </div>
</template>

<script>
import SampleDataModal from '@baserow/modules/core/components/SampleDataModal'

const MAX_FORMATTED_SAMPLE_DATA_LENGTH = 10000

export default {
  name: 'SampleDataViewer',
  components: { SampleDataModal },
  props: {
    sampleData: {
      type: null,
      required: false,
      default: null,
    },
    contentType: {
      type: String,
      required: false,
      default: 'json',
    },
    sampleDataHtml: {
      type: String,
      required: false,
      default: null,
    },
    isError: {
      type: Boolean,
      required: false,
      default: false,
    },
    modalTitle: {
      type: String,
      required: true,
    },
    modalSubtitle: {
      type: String,
      required: true,
    },
  },
  computed: {
    viewerLabel() {
      return this.isError
        ? this.$t('sampleDataViewer.errorLabel')
        : this.$t('sampleDataViewer.payloadLabel')
    },
    showViewerLabel() {
      return this.isError
        ? this.$t('sampleDataViewer.showErrorLabel')
        : this.$t('sampleDataViewer.showPayloadLabel')
    },
    formattedSampleData() {
      return typeof this.sampleData === 'string'
        ? this.sampleData
        : JSON.stringify(this.sampleData, null, 2)
    },
    displayedFormattedSampleData() {
      if (this.formattedSampleData.length <= MAX_FORMATTED_SAMPLE_DATA_LENGTH) {
        return this.formattedSampleData
      }

      return `${this.formattedSampleData.slice(
        0,
        MAX_FORMATTED_SAMPLE_DATA_LENGTH
      )}\n${this.$t('sampleDataViewer.truncatedLabel')}`
    },
  },
  methods: {
    showSampleDataModal() {
      this.$refs.sampleDataModalRef.show()
    },
  },
}
</script>
