<template>
  <div>
    <slot></slot>
    <a
      class="made-with-baserow"
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
      initial-selected-type="public_logo_removal"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal.vue'

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
