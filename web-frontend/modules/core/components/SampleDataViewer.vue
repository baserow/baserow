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
        <pre><code>{{ formattedSampleData }}</code></pre>
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
      :title="modalTitle"
      :subtitle="modalSubtitle"
    />
  </div>
</template>

<script>
import SampleDataModal from '@baserow/modules/core/components/SampleDataModal'

export default {
  name: 'SampleDataViewer',
  components: { SampleDataModal },
  props: {
    sampleData: {
      type: null,
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
  },
  methods: {
    showSampleDataModal() {
      this.$refs.sampleDataModalRef.show()
    },
  },
}
</script>
