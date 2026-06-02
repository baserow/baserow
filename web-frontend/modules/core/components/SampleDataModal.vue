<template>
  <Modal ref="modal" class="sample-data-modal">
    <h2 class="box__title">{{ title }}</h2>
    <div class="sample-data-modal__sub-title">
      {{ subtitle }}
      <Button
        type="secondary"
        icon="iconoir-copy sample-data-modal__button-icon"
        @click="copyToClipboard"
      >
        {{ $t('action.copy') }}
      </Button>
    </div>
    <div class="sample-data-modal__code">
      <pre><code>{{ formattedSampleData }}</code></pre>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'

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
  },
  computed: {
    formattedSampleData() {
      return typeof this.sampleData === 'string'
        ? this.sampleData
        : JSON.stringify(this.sampleData, null, 2)
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
  },
}
</script>
