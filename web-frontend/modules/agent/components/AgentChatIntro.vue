<template>
  <div class="agent-chat__intro">
    <div class="agent-chat__avatar">
      <img :src="agentOrb" alt="" />
    </div>
    <i18n-t scope="global" keypath="agent.talkTo" tag="h1">
      <template #name>
        <span class="agent-chat__intro-name">{{ name }}</span>
      </template>
    </i18n-t>
    <p>{{ $t('agent.chatDescription') }}</p>
  </div>
</template>

<script setup>
import agentOrb from '@baserow/modules/agent/assets/images/agent-orb.svg?url'

/** What an Agent's chat shows before its first message. */
defineProps({ name: { type: String, required: true } })
</script>
