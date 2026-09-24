<template>
  <FormGroup
    class="margin-bottom-2"
    :label="$t('inboundEmailTriggerServiceForm.title')"
    small-label
    required
  >
    <Alert v-if="!defaultValues.email_address" type="warning">
      {{ $t('inboundEmailTriggerServiceForm.notConfigured') }}
    </Alert>

    <template v-else>
      <FormGroup class="margin-bottom-2">
        <RadioGroup
          v-model="isPublishedAddress"
          :options="addressVersions"
          type="button"
        >
        </RadioGroup>
      </FormGroup>

      <a
        v-tooltip="$t('inboundEmailTriggerServiceForm.copyAddress')"
        class="inbound-email-trigger-service-form__copy-address"
        tooltip-position="top"
        @click.stop=";[copyAddressToClipboard(), $refs.addressCopied.show()]"
      >
        <pre><code class="inbound-email-trigger-service-form__email-address">{{ emailAddress }}</code></pre>
        <Copied ref="addressCopied" />
      </a>

      <p class="margin-bottom-1">
        {{ $t('inboundEmailTriggerServiceForm.description') }}
      </p>
      <p v-if="maxMessageSizeMb" class="margin-bottom-1">
        {{
          $t('inboundEmailTriggerServiceForm.limits', {
            size: maxMessageSizeMb,
          })
        }}
      </p>
      <p class="margin-bottom-1">
        {{ $t('inboundEmailTriggerServiceForm.autoForwardTip') }}
      </p>
      <p>
        {{ $t('inboundEmailTriggerServiceForm.secretWarning') }}
      </p>

      <Button
        type="secondary"
        size="small"
        icon="iconoir-refresh"
        :loading="loading"
        @click.prevent="regenerateAddress()"
      >
        {{ $t('inboundEmailTriggerServiceForm.regenerate') }}
      </Button>
    </template>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'CoreInboundEmailTriggerServiceForm',
  mixins: [form],
  props: {
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['values-changed'],
  data() {
    return {
      allowedValues: [],
      values: {},
      // Like the HTTP trigger's `?test=true`, the `test-` prefixed address
      // targets the draft workflow (a test run) and the bare one the
      // published workflow. Default to the test address, as the HTTP trigger
      // form does, since the draft is what the user is editing right here.
      isPublishedAddress: false,
      addressVersions: [
        {
          value: false,
          label: this.$t('inboundEmailTriggerServiceForm.addressVersionTest'),
        },
        {
          value: true,
          label: this.$t(
            'inboundEmailTriggerServiceForm.addressVersionPublished'
          ),
        },
      ],
    }
  },
  computed: {
    emailAddress() {
      return this.isPublishedAddress
        ? this.defaultValues.email_address
        : this.defaultValues.test_email_address
    },
    maxMessageSizeMb() {
      return this.defaultValues.max_message_size_mb
    },
  },
  methods: {
    copyAddressToClipboard() {
      copyToClipboard(this.emailAddress)
    },
    /**
     * The `regenerate_token` flag is deliberately not part of `values`:
     * it's a write-only request field, and keeping it in the form values
     * would re-send it on every subsequent change, regenerating the
     * address each time. It's emitted once instead.
     */
    regenerateAddress() {
      this.$emit('values-changed', { regenerate_token: true })
    },
  },
}
</script>
