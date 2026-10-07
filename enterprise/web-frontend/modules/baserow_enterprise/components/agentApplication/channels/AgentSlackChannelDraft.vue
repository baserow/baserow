<template>
  <div>
    <div class="agent-configuration__hint margin-bottom-2">
      {{ $t('agentChannels.slackCreateHint') }}
    </div>
    <AgentSlackSetupSteps />
  </div>
</template>

<script>
import AgentSlackSetupSteps from '@baserow_enterprise/components/agentApplication/AgentSlackSetupSteps'

export default {
  name: 'AgentSlackChannelDraft',
  components: { AgentSlackSetupSteps },
  props: {
    draft: {
      type: Object,
      required: true,
    },
  },
}
</script>
