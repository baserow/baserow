<template>
  <div class="assistant-onboarding">
    <div class="assistant-onboarding__logo">
      <img :src="image" alt="kuma" width="56" height="56" />
    </div>
    <div class="assistant-onboarding__title">
      <i class="iconoir-magic-wand assistant-onboarding__title-icon"></i>
      Kuma is building your database
    </div>
    <div class="assistant-onboarding__message">
      <div class="assistant-onboarding__loading-wrapper">
        <div class="assistant-onboarding__loading"></div>
      </div>
      <div class="assistant-onboarding__text">
        {{ message }}
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import image from '@baserow_enterprise/assets/images/kuma.svg?url'

export default {
  name: 'AssistantOnboardingMessage',
  computed: {
    ...mapGetters({
      messages: 'assistant/messages',
    }),
    message() {
      const defaultMessage = this.$t('assistantOnboardingMessage.instructing')
      const messages = Array.isArray(this.messages) ? this.messages : []
      const lastReasoning = [...messages]
        .reverse()
        .find(
          (m) =>
            m?.role === 'ai' &&
            m?.reasoning === true &&
            typeof m?.content === 'string' &&
            m.content.trim()
        )
      return lastReasoning?.content ?? defaultMessage
    },
    image() {
      return image
    },
  },
}
</script>
