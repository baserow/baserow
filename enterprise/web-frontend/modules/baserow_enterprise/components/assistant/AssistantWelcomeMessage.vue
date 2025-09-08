<template>
  <div class="assistant__welcome">
    <div class="assistant__welcome-icon">
      <i class="iconoir-message-text"></i>
    </div>
    <h2 class="assistant__welcome-title">
      <span class="assistant__welcome-title-greeting">
        {{ $t('assistantWelcomeMessage.greet', { name }) }},
      </span>
      {{ $t('assistantWelcomeMessage.question') }}
    </h2>
    <p class="assistant__welcome-subtitle">
      {{ $t('assistantWelcomeMessage.subtitle') }}
    </p>
  </div>
</template>

<script>
export default {
  name: 'AssistantWelcomeMessage',
  props: {
    name: {
      type: String,
      default: 'there',
    },
  },
}
</script>
