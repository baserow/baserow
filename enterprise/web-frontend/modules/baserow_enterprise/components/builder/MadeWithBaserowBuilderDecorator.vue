<template>
  <div>
    <slot></slot>
    <a
      class="made-with-baserow"
      title="Open source self-hosted no-code platform"
      :href="showPaidFeaturesModal ? null : 'https://baserow.io/'"
      :target="showPaidFeaturesModal ? null : '_blank'"
      @click="handleMadeWithBaserowClick"
    >
      Made with
      <img
        src="@baserow_enterprise/assets/images/builder/mini_logo.svg"
        alt="Baserow"
      />
    </a>

    <PaidFeaturesModal
      ref="paidFeaturesModal"
      :initial-selected-type="paidFeatureType"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { BuilderBrandingPaidFeature } from '@baserow_enterprise/paidFeatures'

export default {
  components: {
    PaidFeaturesModal,
  },
  props: {
    showPaidFeaturesModal: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    paidFeatureType() {
      return BuilderBrandingPaidFeature.getType()
    },
  },
  methods: {
    handleMadeWithBaserowClick(event) {
      if (this.showPaidFeaturesModal) {
        event.preventDefault()
        this.$refs.paidFeaturesModal.show()
      }
    },
  },
}
</script>
