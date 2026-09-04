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
    <Tabs v-if="hasHtmlTab" header-no-padding content-no-x-padding>
      <Tab title="JSON">
        <div class="sample-data-modal__code">
          <pre><code>{{ displayedFormattedSampleData }}</code></pre>
        </div>
      </Tab>
      <Tab title="HTML">
        <iframe
          v-if="sampleDataHtml"
          class="sample-data-modal__html-preview"
          sandbox=""
          :srcdoc="sampleDataHtml"
          :title="title"
        ></iframe>
        <div v-else class="sample-data-modal__notice">
          {{ $t('sampleDataViewer.noHtmlContent') }}
        </div>
      </Tab>
    </Tabs>
    <div v-else class="sample-data-modal__code">
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
    /**
     * The content type of the sample data. When it's 'html', the modal
     * shows a JSON and an HTML tab instead of only the JSON payload.
     */
    contentType: {
      type: String,
      required: false,
      default: 'json',
    },
    /**
     * The HTML document rendered in the HTML tab when the content type is
     * 'html'. It's rendered in a fully sandboxed iframe because the content
     * is untrusted (e.g. a received email).
     */
    sampleDataHtml: {
      type: String,
      required: false,
      default: null,
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
    hasHtmlTab() {
      return this.contentType === 'html'
    },
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
