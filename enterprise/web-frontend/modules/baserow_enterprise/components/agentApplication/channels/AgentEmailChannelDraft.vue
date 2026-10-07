<template>
  <div>
    <div class="agent-configuration__hint margin-bottom-2">
      {{ $t('agentChannels.emailCreateHint') }}
    </div>
    <Alert v-if="!available" type="warning">
      <p>{{ $t('agentChannels.emailUnavailable') }}</p>
    </Alert>
  </div>
</template>

<script>
export default {
  name: 'AgentEmailChannelDraft',
  props: {
    draft: {
      type: Object,
      required: true,
    },
  },
  computed: {
    available() {
      return this.$store.getters['settings/get']?.inbound_email_enabled === true
    },
  },
}
</script>
