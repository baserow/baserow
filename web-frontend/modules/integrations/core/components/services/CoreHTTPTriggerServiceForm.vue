<template>
  <FormGroup
    class="margin-bottom-2"
    :label="$t('coreHTTPTriggerServiceForm.title')"
    small-label
    required
  >
    <FormGroup class="margin-bottom-2">
      <RadioGroup v-model="isPublishedUrl" :options="urlVersions" type="button">
      </RadioGroup>
    </FormGroup>

    <a
      v-tooltip="$t('coreHTTPTriggerServiceForm.copyUrl')"
      class="webhook-service-form__copy-url"
      tooltip-position="top"
      @click.stop=";[copyToClipboard(), $refs.webhookCopied.show()]"
    >
      <pre><code class="webhook-service-form__webhook-url">{{ webhookUrl }}</code></pre>
      <Copied ref="webhookCopied" />
    </a>

    <p>{{ $t('coreHTTPTriggerServiceForm.description') }}</p>

    <FormGroup
      small-label
      required
      :label="$t('coreHTTPTriggerServiceForm.methodsOptionLabel')"
    >
      <Dropdown
        v-model="values.exclude_get"
        :show-search="false"
        @input="values.exclude_get = $event"
      >
        <DropdownItem
          v-for="option in methodOptions"
          :key="option.label"
          :name="option.label"
          :value="option.value"
        >
        </DropdownItem>
      </Dropdown>

      <p>{{ $t('coreHTTPTriggerServiceForm.methodsOptionDescription') }}</p>
    </FormGroup>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { WEBHOOK_EXCLUDE_METHOD_OPTIONS } from '@baserow/modules/integrations/core/enums'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'CoreHTTPTriggerServiceForm',
  mixins: [form],
  data() {
    return {
      allowedValues: ['exclude_get'],
      values: {
        exclude_get: this.defaultValues.exclude_get,
      },
      isPublishedUrl: false,
      urlVersions: [
        {
          value: false,
          label: this.$t('coreHTTPTriggerServiceForm.urlVersionTest'),
        },
        {
          value: true,
          label: this.$t('coreHTTPTriggerServiceForm.urlVersionPublished'),
        },
      ],
    }
  },
  computed: {
    webhookUrl() {
      if (this.defaultValues.uid) {
        const url = `${this.$config.PUBLIC_BACKEND_URL}/api/webhooks/${this.defaultValues.uid}/`
        if (!this.isPublishedUrl) {
          return `${url}?test=true`
        } else {
          return url
        }
      }
      return null
    },
    methodOptions() {
      return [
        {
          label: this.$t('coreHTTPTriggerServiceForm.methodsOptionAll'),
          value: WEBHOOK_EXCLUDE_METHOD_OPTIONS.ALL,
        },
        {
          label: this.$t('coreHTTPTriggerServiceForm.methodsOptionExcludeGet'),
          value: WEBHOOK_EXCLUDE_METHOD_OPTIONS.EXCLUDE_GET,
        },
      ]
    },
  },
  methods: {
    copyToClipboard() {
      copyToClipboard(this.webhookUrl)
    },
  },
}
</script>
