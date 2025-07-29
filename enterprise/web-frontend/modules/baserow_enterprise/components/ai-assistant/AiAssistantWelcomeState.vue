<template>
  <div class="ai-assistant__welcome">
    <div class="ai-assistant__welcome-icon">
      <i class="iconoir-message-text"></i>
    </div>
    <h2 class="ai-assistant__welcome-title">
      <span class="ai-assistant__welcome-title-greeting">
        Hey {{ userFirstName }},
      </span>
      how can I help?
    </h2>
    <p class="ai-assistant__welcome-subtitle">
      I'm here to support you in handling your data.<br />
      Choose from the prompts below or just tell me what you need!
    </p>

    <!-- Suggestions -->
    <div class="ai-assistant__suggestions">
      <div
        v-for="suggestion in suggestions"
        :key="suggestion.id"
        class="ai-assistant__suggestion-card"
        @click="$emit('send-message', suggestion.text)"
      >
        <div class="ai-assistant__suggestion-icon">
          <i :class="suggestion.icon"></i>
        </div>
        <div class="ai-assistant__suggestion-content">
          <h3 class="ai-assistant__suggestion-title">
            {{ suggestion.label }}
          </h3>
          <p class="ai-assistant__suggestion-description">
            {{ suggestion.description }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AiAssistantWelcomeState',
  props: {
    userFirstName: {
      type: String,
      default: 'there',
    },
    suggestions: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['send-message'],
}
</script>
