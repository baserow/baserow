<template>
  <div class="onboarding-user-preview__container">
    <div class="onboarding-user-preview__wrapper">
      <div class="onboarding-user-preview">
        <div
          class="onboarding-user-preview__initials"
          :class="{ 'onboarding-user-preview__initials--colored': team }"
        >
          {{ name.toString().toUpperCase().split('')[0] }}
        </div>
        <div class="onboarding-user-preview__box">
          <div class="onboarding-user-preview__head">
            <div class="onboarding-user-preview__name">{{ name }}</div>
          </div>
          <div class="onboarding-user-preview__body">
            <div
              class="onboarding-user-preview__team"
              :class="{ 'onboarding-user-preview__team--empty': !team }"
            >
              <Badge
                v-if="team"
                size="large"
                bold
                rounded
                indicator
                color="cyan"
                >{{ team }}</Badge
              >
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { MoreOnboardingType } from '@baserow/modules/core/onboardingTypes'

export default {
  name: 'UserPreview',
  props: {
    data: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({
      name: 'auth/getName',
    }),
    role() {
      return this.data[MoreOnboardingType.getType()]?.role
    },
    team() {
      return this.data[MoreOnboardingType.getType()]?.team
    },
  },
}
</script>
