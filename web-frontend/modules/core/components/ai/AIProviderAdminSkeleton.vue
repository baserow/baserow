<template>
  <div class="skeleton" aria-hidden="true">
    <section class="ai-provider-feature-settings">
      <div class="ai-provider-feature-settings__heading">
        <div class="ai-provider-feature-settings__title">
          <SkeletonBlock width="180px" height="18px"></SkeletonBlock>
        </div>
        <div class="ai-provider-feature-settings__description">
          <SkeletonBlock width="320px" height="10px"></SkeletonBlock>
        </div>
      </div>
      <div
        v-for="feature in featureCount"
        :key="`feature-${feature}`"
        class="ai-provider-feature-settings__row"
      >
        <div class="ai-provider-feature-settings__feature">
          <SkeletonBlock width="140px"></SkeletonBlock>
          <SkeletonBlock width="220px" height="10px"></SkeletonBlock>
        </div>
        <SkeletonBlock height="36px"></SkeletonBlock>
      </div>
    </section>
    <div class="ai-provider-admin__list">
      <section
        v-for="provider in providerCount"
        :key="`provider-${provider}`"
        class="ai-provider-card"
      >
        <header class="ai-provider-card__header">
          <div class="ai-provider-card__heading">
            <div class="ai-provider-card__title-row">
              <SkeletonBlock width="160px" height="18px"></SkeletonBlock>
              <SkeletonBlock width="60px" height="16px"></SkeletonBlock>
            </div>
          </div>
          <div class="ai-provider-card__actions">
            <SkeletonBlock width="24px" height="24px"></SkeletonBlock>
          </div>
        </header>
        <div class="ai-provider-card__models">
          <div
            v-for="model in modelCount"
            :key="`model-${model}`"
            class="ai-provider-model"
          >
            <div class="ai-provider-model__identity">
              <div class="ai-provider-model__name">
                <SkeletonBlock width="200px"></SkeletonBlock>
              </div>
              <div class="ai-provider-model__features">
                <SkeletonBlock width="140px" height="10px"></SkeletonBlock>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
/**
 * The AI providers admin page while the providers and their models are fetched.
 * It mirrors the feature settings and the provider cards, so that the page keeps
 * its shape once they arrive.
 */
export default {
  name: 'AIProviderAdminSkeleton',
  props: {
    providerCount: {
      required: false,
      type: Number,
      default: 1,
    },
    modelCount: {
      required: false,
      type: Number,
      default: 2,
    },
    featureCount: {
      required: false,
      type: Number,
      default: 1,
    },
  },
}
</script>
