<template>
  <FormGroup
    class="margin-bottom-2"
    :label="$t('inboundEmailTriggerServiceForm.title')"
    small-label
    required
  >
    <Alert v-if="!emailAddress" type="warning">
      {{ $t('inboundEmailTriggerServiceForm.notConfigured') }}
    </Alert>

    <template v-else>
      <a
        v-tooltip="$t('inboundEmailTriggerServiceForm.copyAddress')"
        class="inbound-email-trigger-service-form__copy-address"
        tooltip-position="top"
        @click.stop=";[copyAddressToClipboard(), $refs.addressCopied.show()]"
      >
        <pre><code class="inbound-email-trigger-service-form__email-address">{{ emailAddress }}</code></pre>
        <Copied ref="addressCopied" />
      </a>

      <p>{{ $t('inboundEmailTriggerServiceForm.description') }}</p>
      <p>{{ $t('inboundEmailTriggerServiceForm.autoForwardTip') }}</p>
      <p>{{ $t('inboundEmailTriggerServiceForm.secretWarning') }}</p>

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
  data() {
    return {
      allowedValues: [],
      values: {},
    }
  },
  computed: {
    emailAddress() {
      return this.defaultValues.email_address
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
