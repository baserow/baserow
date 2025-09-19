<template>
  <FormGroup
    class="margin-bottom-2"
    :label="$t('coreHTTPWebhookServiceForm.title')"
    small-label
    required
  >
    <FormGroup class="margin-bottom-2">
      <RadioGroup v-model="isPublishedUrl" :options="urlVersions" type="button">
      </RadioGroup>
    </FormGroup>

    <pre><code class="webhook-service-form__webhook-url">{{ webhookUrl }}</code></pre>

    <div class="webhook-service-form__copy-url">
      {{ $t('coreHTTPWebhookServiceForm.copyUrl') }}
      <ButtonIcon
        icon="iconoir-copy"
        :title="$t('coreHTTPWebhookServiceForm.copyUrl')"
        size="small"
        @click="copyToClipboard"
      />
    </div>

    <p>{{ $t('coreHTTPWebhookServiceForm.description') }}</p>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'CoreHTTPWebhookServiceForm',
  mixins: [form],
  data() {
    return {
      allowedValues: [],
      values: {},
      isPublishedUrl: true,
      urlVersions: [
        {
          value: true,
          label: this.$t('coreHTTPWebhookServiceForm.urlVersionPublished'),
        },
        {
          value: false,
          label: this.$t('coreHTTPWebhookServiceForm.urlVersionTest'),
        },
      ],
    }
  },
  computed: {
    webhookUrl() {
      if (this.defaultValues.uid) {
        const url = `${this.$config.PUBLIC_BACKEND_URL}/api/webhooks/${this.defaultValues.uid}/`
        if (!this.isPublishedUrl) {
          return `${url}?baserow_test=true`
        } else {
          return url
        }
      }
      return null
    },
  },
  methods: {
    async copyToClipboard() {
      try {
        await navigator.clipboard.writeText(this.webhookUrl)
        this.$store.dispatch('toast/success', {
          title: this.$t('coreHTTPWebhookServiceForm.urlCopied'),
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
