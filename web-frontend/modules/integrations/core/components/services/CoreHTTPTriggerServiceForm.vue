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

    <pre><code class="webhook-service-form__webhook-url">{{ webhookUrl }}</code></pre>

    <div class="webhook-service-form__copy-url">
      {{ $t('coreHTTPTriggerServiceForm.copyUrl') }}
      <ButtonIcon
        icon="iconoir-copy"
        :title="$t('coreHTTPTriggerServiceForm.copyUrl')"
        size="small"
        @click="copyToClipboard"
      />
    </div>

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
import { notifyIf } from '@baserow/modules/core/utils/error'
import { WEBHOOK_EXCLUDE_METHOD_OPTIONS } from '@baserow/modules/integrations/core/enums'

export default {
  name: 'CoreHTTPTriggerServiceForm',
  mixins: [form],
  data() {
    return {
      allowedValues: ['exclude_get'],
      values: {
        exclude_get: this.defaultValues.exclude_get,
      },
      isPublishedUrl: true,
      urlVersions: [
        {
          value: true,
          label: this.$t('coreHTTPTriggerServiceForm.urlVersionPublished'),
        },
        {
          value: false,
          label: this.$t('coreHTTPTriggerServiceForm.urlVersionTest'),
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
    async copyToClipboard() {
      try {
        await navigator.clipboard.writeText(this.webhookUrl)
        this.$store.dispatch('toast/success', {
          title: this.$t('coreHTTPTriggerServiceForm.urlCopied'),
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
