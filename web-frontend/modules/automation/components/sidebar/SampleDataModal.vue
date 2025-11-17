<template>
  <Modal class="sample-data-modal">
    <h2 class="box__title">{{ title }}</h2>
    <div class="sample-data-modal__sub-title">
      {{ $t('simulateDispatch.sampleDataModalSubTitle') }}
      <Button
        type="secondary"
        icon="iconoir-copy simulate-dispatch-node__button-icon"
        @click="copyToClipboard"
      >
        {{ $t('simulateDispatch.sampleDataCopy') }}
      </Button>
    </div>
    <div class="sample-data-modal__code">
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
      type: null,
      required: true,
    },
    title: {
      type: String,
      required: true,
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
