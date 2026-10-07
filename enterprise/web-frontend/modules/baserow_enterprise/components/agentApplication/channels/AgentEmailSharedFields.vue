<template>
  <div>
    <div
      class="agent-configuration__switch-row agent-configuration__switch-row--plain"
    >
      <i class="agent-configuration__switch-icon iconoir-shield-check"></i>
      <div class="agent-configuration__switch-text">
        <div class="agent-configuration__switch-title">
          {{ $t('agentChannels.requireApproval') }}
        </div>
        <div class="agent-configuration__switch-description">
          {{ $t('agentChannels.requireApprovalDescription') }}
        </div>
      </div>
      <SwitchInput
        small
        :value="channel.config.require_approval !== false"
        :disabled="!canUpdate"
        @input="$emit('update:require-approval', $event)"
      ></SwitchInput>
    </div>
    <FormGroup
      small-label
      :label="$t('agentChannels.allowedSenderDomainsLabel')"
      :helper-text="$t('agentChannels.allowedSenderDomainsHelp')"
      class="margin-bottom-2 margin-top-2"
    >
      <FormInput
        :model-value="allowedSenderDomains"
        :disabled="!canUpdate"
        :placeholder="$t('agentChannels.allowedSenderDomainsPlaceholder')"
        @update:model-value="$emit('update:allowed-sender-domains', $event)"
      ></FormInput>
    </FormGroup>
  </div>
</template>

<script>
export default {
  name: 'AgentEmailSharedFields',
  props: {
    channel: { type: Object, required: true },
    canUpdate: { type: Boolean, required: false, default: false },
    allowedSenderDomains: { type: String, required: false, default: '' },
  },
  emits: ['update:require-approval', 'update:allowed-sender-domains'],
}
</script>
