<template>
  <div
    v-tooltip="tooltipText"
    class="dashboard-sharing__option"
    :class="{ 'dashboard-sharing__option--disabled': !hasPremiumFeatures }"
    @click="click"
  >
    <SwitchInput
      small
      :value="!dashboard.show_logo"
      :disabled="!hasPremiumFeatures"
      @input="update('show_logo', !$event)"
    >
      <img
        class="switch__icon"
        src="@baserow/modules/core/static/img/baserow-icon.svg?url"
      />
      <span>{{ $t('premiumDashboardShareOptions.hideLogo') }}</span>
      <i v-if="!hasPremiumFeatures" class="deactivated-label iconoir-lock" />
    </SwitchInput>

    <PaidFeaturesModal
      v-if="!hasPremiumFeatures"
      ref="paidFeaturesModal"
      :workspace="dashboard.workspace"
      initial-selected-type="public_logo_removal"
    ></PaidFeaturesModal>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import PremiumDashboardService from '@baserow_premium/services/dashboard'
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  dashboard: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['update-dashboard'])

const { t } = useI18n()
const { $client, $hasFeature } = useNuxtApp()

const paidFeaturesModal = ref(null)

const hasPremiumFeatures = computed(() => {
  return $hasFeature(PremiumFeatures.PREMIUM, props.dashboard.workspace.id)
})

const tooltipText = computed(() => {
  return hasPremiumFeatures.value ? null : t('premium.deactivated')
})

const update = async (key, value) => {
  try {
    // Optimistically apply the change, the request is expected to succeed.
    emit('update-dashboard', { [key]: value })
    await PremiumDashboardService($client).update(props.dashboard.id, {
      [key]: value,
    })
  } catch (error) {
    // Roll the change back if it didn't.
    emit('update-dashboard', { [key]: !value })
    notifyIf(error, 'application')
  }
}

const click = () => {
  if (!hasPremiumFeatures.value) {
    paidFeaturesModal.value.show()
  }
}
</script>
