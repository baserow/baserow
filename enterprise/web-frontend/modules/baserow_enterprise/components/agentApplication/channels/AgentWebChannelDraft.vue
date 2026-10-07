<template>
  <div class="agent-configuration__hint margin-bottom-2">
    {{
      draft.type === 'website'
        ? $t('agentChannels.websiteCreateHint')
        : $t('agentChannels.webCreateHint')
    }}
  </div>
</template>

<script>
export default {
  name: 'AgentWebChannelDraft',
  props: {
    draft: {
      type: Object,
      required: true,
    },
  },
}
</script>
