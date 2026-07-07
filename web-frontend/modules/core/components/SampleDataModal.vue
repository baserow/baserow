<template>
  <Modal ref="modal" class="sample-data-modal">
    <h2 class="box__title">{{ title }}</h2>
    <div class="sample-data-modal__sub-title">
      {{ subtitle }}
      <div class="sample-data-modal__actions">
        <Button
          type="secondary"
          icon="iconoir-download sample-data-modal__button-icon"
          @click="downloadSampleData"
        >
          {{ $t('sampleDataViewer.downloadFullPayload') }}
        </Button>
        <Button
          type="secondary"
          icon="iconoir-copy sample-data-modal__button-icon"
          @click="copyToClipboard"
        >
          {{ $t('action.copy') }}
        </Button>
      </div>
    </div>
    <div
      v-if="isFormattedSampleDataTruncated"
      class="sample-data-modal__notice"
    >
      {{
        $t('sampleDataViewer.truncatedPayloadWarning', {
          size: maxFormattedSampleDataLength.toLocaleString(),
        })
      }}
    </div>
    <div class="sample-data-modal__code">
      <pre><code>{{ displayedFormattedSampleData }}</code></pre>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'

const MAX_FORMATTED_SAMPLE_DATA_LENGTH = 10000

export default {
  name: 'SampleDataModal',
  mixins: [modal],
  props: {
    sampleData: {
      type: null,
      required: true,
    },
    title: {
      type: String,
      required: true,
    },
    subtitle: {
      type: String,
      required: true,
    },
    filename: {
      type: String,
      required: false,
      default: 'sample-data.json',
    },
  },
  computed: {
    maxFormattedSampleDataLength() {
      return MAX_FORMATTED_SAMPLE_DATA_LENGTH
    },
    formattedSampleData() {
      return typeof this.sampleData === 'string'
        ? this.sampleData
        : JSON.stringify(this.sampleData, null, 2)
    },
    isFormattedSampleDataTruncated() {
      return this.formattedSampleData.length > this.maxFormattedSampleDataLength
    },
    displayedFormattedSampleData() {
      if (!this.isFormattedSampleDataTruncated) {
        return this.formattedSampleData
      }

      return `${this.formattedSampleData.slice(
        0,
        this.maxFormattedSampleDataLength
      )}\n${this.$t('sampleDataViewer.truncatedLabel')}`
    },
  },
  methods: {
    async copyToClipboard() {
      try {
        await navigator.clipboard.writeText(this.formattedSampleData)
        this.$store.dispatch('toast/success', {
          title: this.$t('copied.label'),
        })
      } catch (error) {
        notifyIf(error)
      }
    },
    downloadSampleData() {
      const blob = new Blob([this.formattedSampleData], {
        type: 'application/json;charset=utf-8',
      })
      const data = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style = 'display: none'
      a.href = data
      a.download = this.filename
      document.body.appendChild(a)
      a.click()

      setTimeout(() => {
        document.body.removeChild(a)
        window.URL.revokeObjectURL(data)
      }, 500)
    },
  },
}
</script>
