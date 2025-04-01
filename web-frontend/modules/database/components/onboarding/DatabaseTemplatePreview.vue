<template>
  <div :class="{ 'onboarding-tool-preview': true }">
    <div
      ref="inner"
      class="onboarding-tool-preview__inner onboarding-tool-preview__inner--reserve-space-right"
    >
      <TemplatePreview :template="template"></TemplatePreview>
    </div>
  </div>
</template>

<script>
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes'

export default {
  name: 'DatabaseTemplatePreview',
  components: { TemplatePreview },
  props: {
    data: {
      type: Object,
      required: true,
    },
  },
  computed: {
    template() {
      return this.data[DatabaseOnboardingType.getType()].template
    },
  },
}
</script>
