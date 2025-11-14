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
      {{ $t('assistantWelcomeMessage.subtitle') }}
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
      const applicationType = this.uiContext.applicationType || null
      console.log(applicationType)
      const mapping = {
        null: [
          {
            id: 'database',
            icon: 'iconoir-view-grid',
            title: 'Create a database',
            prompt: 'Build a project management database.',
          },
          {
            id: 'automation',
            icon: 'baserow-icon-automation',
            title: 'Create an automation',
            prompt:
              'Create an automation that every Tuesday in the morning ask in the Slack developers channel if there is anything to demo.',
          },
        ],
        database: [
          {
            id: 'form',
            icon: 'iconoir-submit-document',
            title: 'Create a form',
            prompt: 'Create a form for this table.',
          },
          {
            id: 'filter',
            icon: 'iconoir-filter',
            title: 'Create a filter',
            prompt: 'Show only rows where the primary field is empty.',
          },
          {
            id: 'table',
            icon: 'iconoir-view-grid',
            title: 'Create a table',
            prompt: 'Create a new table named tasks.',
          },
        ],
      }
      return mapping[applicationType] || []
    },
  },
}
</script>
