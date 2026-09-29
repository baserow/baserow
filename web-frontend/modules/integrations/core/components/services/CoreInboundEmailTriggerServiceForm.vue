<template>
  <FormGroup
    class="margin-bottom-2"
    :label="$t('inboundEmailTriggerServiceForm.title')"
    small-label
    required
  >
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

    <Alert type="info-primary" class="margin-top-1 margin-bottom-2">
      <p>{{ $t('inboundEmailTriggerServiceForm.infoDescription') }}</p>
    </Alert>

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
      :loading="regenerating"
      @click.prevent="regenerateAddress()"
    >
      {{ $t('inboundEmailTriggerServiceForm.regenerate') }}
    </Button>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'CoreInboundEmailTriggerServiceForm',
  mixins: [form],
  emits: ['values-changed'],
  data() {
    return {
      allowedValues: [],
      values: {},
      // Whether the address is being regenerated. This is the form's own
      // state, not the node's loading flag: that flag is also set while any
      // other change to the node is saved, such as a new label, and the
      // button should only spin for its own request.
      regenerating: false,
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
     * address each time. It's emitted once instead, flagged as immediate:
     * value changes are normally debounced to batch keystrokes, which for
     * a button click only delays the spinner and the request. The side
     * panel calls `onSettled` once the request has succeeded or failed,
     * which ends the button's loading state either way.
     */
    regenerateAddress() {
      this.regenerating = true
      this.$emit(
        'values-changed',
        { regenerate_token: true },
        {
          immediate: true,
          onSettled: () => {
            this.regenerating = false
          },
        }
      )
    },
  },
}
</script>
