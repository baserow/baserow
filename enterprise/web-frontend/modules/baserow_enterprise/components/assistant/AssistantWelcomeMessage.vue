<template>
  <div class="assistant__welcome">
    <div class="assistant__welcome-kuma">
      <video
        :src="video"
        autoplay
        loop
        muted
        playsinline
        preload="auto"
        :poster="image"
        controlslist="nodownload nofullscreen noplaybackrate noremoteplayback"
        disablepictureinpicture
        oncontextmenu="return false;"
        aria-hidden="true"
        role="presentation"
        class="assistant__welcome-video"
      >
        <img :src="image" />
      </video>
    </div>
    <h2 class="assistant__welcome-title">
      <span class="assistant__welcome-title-greeting">
        {{ $t('assistantWelcomeMessage.greet', { name }) }},
      </span>
      {{ $t('assistantWelcomeMessage.question') }}
    </h2>
    <p class="assistant__welcome-subtitle">
      {{
        suggestions.length === 0
          ? $t('assistantWelcomeMessage.subtitleWithoutSuggestions')
          : $t('assistantWelcomeMessage.subtitle')
      }}
    </p>
    <a
      v-for="suggestion in suggestions"
      :key="suggestion.id"
      class="assistant__suggestion"
      @click="$emit('prompt', suggestion.prompt)"
    >
      <div class="assistant__suggestion-icon-wrapper">
        <div class="assistant__suggestion-icon">
          <i :class="suggestion.icon"></i>
        </div>
      </div>
      <div class="assistant__suggestion-text">
        <div class="assistant__suggestion-title">{{ suggestion.title }}</div>
        <div class="assistant__suggestion-description">
          {{ suggestion.prompt }}
        </div>
      </div>
    </a>
  </div>
</template>

<script>
import video from '@baserow_enterprise/assets/videos/kuma.mp4'
import image from '@baserow_enterprise/assets/images/kuma.svg'

export default {
  name: 'AssistantWelcomeMessage',
  props: {
    name: {
      type: String,
      default: 'there',
    },
    uiContext: {
      type: Object,
      default: () => ({}),
    },
  },
  computed: {
    video() {
      return video
    },
    image() {
      return image
    },
    suggestions() {
      let type = this.uiContext.applicationType || null
      if (this.uiContext.table) {
        type = 'table'
      }
      const mapping = {
        null: [
          {
            id: 'database',
            icon: 'iconoir-view-grid',
            title: this.$t('assistantWelcomeMessage.promptCreateDatabaseTitle'),
            prompt: this.$t(
              'assistantWelcomeMessage.promptCreateDatabasePrompt'
            ),
          },
          {
            id: 'automation',
            icon: 'baserow-icon-automation',
            title: this.$t(
              'assistantWelcomeMessage.promptCreateAutomationTitle'
            ),
            prompt: this.$t(
              'assistantWelcomeMessage.promptCreateAutomationPrompt'
            ),
          },
          {
            id: 'how',
            icon: 'iconoir-send-mail',
            title: this.$t('assistantWelcomeMessage.promptInviteUsersTitle'),
            prompt: this.$t('assistantWelcomeMessage.promptInviteUsersPrompt'),
          },
        ],
        database: [
          {
            id: 'table',
            icon: 'iconoir-view-grid',
            title: this.$t('assistantWelcomeMessage.promptCreateTableTitle'),
            prompt: this.$t('assistantWelcomeMessage.promptCreateTablePrompt'),
          },
          {
            id: 'which-tables',
            icon: 'iconoir-view-grid',
            title: this.$t('assistantWelcomeMessage.promptWhichTablesTitle'),
            prompt: this.$t('assistantWelcomeMessage.promptWhichTablesPrompt'),
          },
        ],
        table: [
          {
            id: 'form',
            icon: 'iconoir-submit-document',
            title: this.$t('assistantWelcomeMessage.promptCreateFormTitle'),
            prompt: this.$t('assistantWelcomeMessage.promptCreateFormPrompt'),
          },
          {
            id: 'filter',
            icon: 'iconoir-filter',
            title: this.$t('assistantWelcomeMessage.promptCreateFilterTitle'),
            prompt: this.$t('assistantWelcomeMessage.promptCreateFilterPrompt'),
          },
          {
            id: 'table',
            icon: 'iconoir-view-grid',
            title: this.$t('assistantWelcomeMessage.promptCreateTableTitle'),
            prompt: this.$t('assistantWelcomeMessage.promptCreateTablePrompt'),
          },
        ],
      }
      return mapping[type] || []
    },
  },
}
</script>
