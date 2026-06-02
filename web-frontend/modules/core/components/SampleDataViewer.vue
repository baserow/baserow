<template>
  <div v-if="sampleData" class="sample-data-viewer">
    <div
      :class="{
        'sample-data-viewer__sample--error': isError,
      }"
    >
      <div class="sample-data-viewer__label">
        {{ isError ? errorLabel : payloadLabel }}
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
      {{ isError ? showErrorLabel : showPayloadLabel }}
    </Button>

    <SampleDataModal
      ref="sampleDataModalRef"
      :sample-data="sampleData"
      :title="modalTitle"
      :subtitle="modalSubtitle"
      :copy-label="copyLabel"
      :copied-toast-title="copiedToastTitle"
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
    payloadLabel: {
      type: String,
      required: true,
    },
    errorLabel: {
      type: String,
      required: true,
    },
    showPayloadLabel: {
      type: String,
      required: true,
    },
    showErrorLabel: {
      type: String,
      required: true,
    },
    modalTitle: {
      type: String,
      required: true,
    },
    modalSubtitle: {
      type: String,
      required: true,
    },
    copyLabel: {
      type: String,
      required: true,
    },
    copiedToastTitle: {
      type: String,
      required: true,
    },
  },
  computed: {
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
