<template>
  <Modal class="sample-data-modal">
    <h2 class="box__title">{{ title }}</h2>
    <div class="sample-data-modal__sub-title">JSON payload</div>
    <div class="sample-data-modal__code">
      <Button
        class="sample-data-modal__copy-button"
        type="secondary"
        icon="iconoir-copy simulate-dispatch-node__button-icon"
        @click="copyToClipboard"
      >
        {{ $t('simulateDispatch.sampleDataCopy') }}
      </Button>
      <pre><code>{{ sampleData }}</code></pre>
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
      type: [Object, Array],
      required: true,
    },
    title: {
      type: String,
      required: true,
    },
  },
  computed: {
    subTitle() {
      return this.$t(`simulateDispatch.sampleDataModalSubTitle`)
    },
  },
  methods: {
    async copyToClipboard() {
      try {
        await navigator.clipboard.writeText(
          JSON.stringify(this.sampleData, null, 2)
        )
        this.$store.dispatch('toast/success', {
          title: this.$t('simulateDispatch.sampleDataCopied'),
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
