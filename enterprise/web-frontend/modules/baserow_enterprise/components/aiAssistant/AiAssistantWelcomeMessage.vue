<template>
  <div class="ai-assistant__welcome">
    <div class="ai-assistant__welcome-icon">
      <i class="iconoir-message-text"></i>
    </div>
    <h2 class="ai-assistant__welcome-title">
      <span class="ai-assistant__welcome-title-greeting">
        {{ $t('aiAssistantWelcomeMessage.greet', { name }) }},
      </span>
      {{ $t('aiAssistantWelcomeMessage.question') }}
    </h2>
    <p class="ai-assistant__welcome-subtitle">
      {{ $t('aiAssistantWelcomeMessage.subtitle') }}
    </p>
  </div>
</template>

<script>
export default {
  name: 'AiAssistantWelcomeMessage',
  props: {
    name: {
      type: String,
      default: 'there',
    },
  },
}
</script>
