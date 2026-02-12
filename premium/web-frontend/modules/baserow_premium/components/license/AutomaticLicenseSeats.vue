<template>
  <div class="license-detail__available-seats">
    <p>
      {{ licenseType.getLicenseDescription(license) }}
    </p>
    <ProgressBar
      :show-overflow="true"
      :value="paidSeatsUsedPercentage"
      :show-value="false"
    >
    </ProgressBar>
    <div class="license-detail__available-seats-status">
      {{ paidSeatsStatus }}
    </div>
    <div
      v-if="overSoftLimit"
      class="delete-section margin-bottom-0 margin-top-4"
    >
      <div class="delete-section__label">
        <div class="delete-section__label-icon">
          <i class="iconoir-warning-triangle"></i>
        </div>
        {{ $t('license.moreSeatsNeededTitle') }}
      </div>
      <p class="delete-section__description">
        {{ licenseType.getLicenseSeatOverflowWarning(license) }}
      </p>
      <Button
        type="secondary"
        tag="a"
        href="https://tcr-cc.com/contact-sales"
        target="_blank"
      >
        {{ $t('license.contactSalesMoreSeats') }}
      </Button>
    </div>
  </div>
</template>
<script>
import ProgressBar from '@baserow/modules/core/components/ProgressBar'

export default {
  name: 'AutomaticLicenseSeats',
  components: { ProgressBar },
  props: {
    license: {
      type: Object,
      required: true,
    },
  },
  computed: {
    paidSeatsStatus() {
      return this.$t('license.automaticSeatsProgressBarStatus', {
        seats: this.license.seats,
        seats_taken: this.license.seats_taken,
        free_users_count: this.license.free_users_count || 0,
      })
    },
    paidSeatsUsedPercentage() {
      return (this.license.seats_taken / this.license.seats) * 100
    },
    overSoftLimit() {
      return this.license.seats_taken > this.license.seats
    },
    licenseType() {
      return this.$registry.get('license', this.license.product_code)
    },
  },
}
</script>
