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
  },
  computed: {
    video() {
      return video
    },
    image() {
      return image
    },
  },
}
</script>
