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

    <FormGroup
      class="margin-bottom-2"
      small-label
      :label="$t('coreHTTPTriggerServiceForm.responseOptionsLabel')"
    >
      <Checkbox v-model="values.wait_for_response">
        {{ $t('coreHTTPTriggerServiceForm.waitForResponse') }}
      </Checkbox>
    </FormGroup>

    <FormGroup
      v-if="values.wait_for_response"
      class="margin-bottom-2"
      small-label
      required
      :label="$t('coreHTTPTriggerServiceForm.responseTimeout')"
      :error-message="getFirstErrorMessage('response_timeout_seconds')"
    >
      <FormInput
        v-model="v$.values.response_timeout_seconds.$model"
        :to-value="(value) => parseInt(value)"
        type="number"
      >
        <template #suffix>{{
          $t('coreHTTPTriggerServiceForm.seconds')
        }}</template>
      </FormInput>
    </FormGroup>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { WEBHOOK_EXCLUDE_METHOD_OPTIONS } from '@baserow/modules/integrations/core/enums'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import { useVuelidate } from '@vuelidate/core'
import {
  helpers,
  integer,
  maxValue,
  minValue,
  required,
} from '@vuelidate/validators'

export default {
  name: 'CoreHTTPTriggerServiceForm',
  components: { Checkbox },
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'exclude_get',
        'wait_for_response',
        'response_timeout_seconds',
      ],
      values: {
        exclude_get: this.defaultValues.exclude_get,
        wait_for_response: false,
        response_timeout_seconds: 30,
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
        const url = `${this.$config.public.publicBackendUrl}/api/webhooks/${this.defaultValues.uid}/`
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
  validations() {
    return {
      values: {
        response_timeout_seconds: {
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 120 }),
            maxValue(120)
          ),
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
        },
      },
    }
  },
}
</script>
