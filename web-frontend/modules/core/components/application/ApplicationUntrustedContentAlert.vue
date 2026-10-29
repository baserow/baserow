<template>
  <Alert
    v-if="contentOwner?.untrusted_content"
    v-tooltip="message"
    type="warning"
    role="alert"
    :aria-label="message"
    :class="{ header__alert: compact }"
  >
    <span :class="{ 'header__alert-label': compact }">{{
      compact ? $t('applicationUntrustedContentAlert.title') : message
    }}</span>
    <a
      href="#"
      :class="{ 'margin-left-1': !compact }"
      @click.prevent="reviewModal.show()"
      >{{ $t('applicationUntrustedContentAlert.review') }}</a
    >
  </Alert>
  <UntrustedContentReviewModal
    ref="reviewModal"
    :report="contentOwner?.import_report || []"
    :can-trust="canTrust"
    :trust-content="trustContent"
  />
</template>

<script setup>
import { ref } from 'vue'
import Alert from '@baserow/modules/core/components/Alert'
import UntrustedContentReviewModal from '@baserow/modules/core/components/application/UntrustedContentReviewModal'

defineProps({
  compact: { type: Boolean, default: true },
  contentOwner: { type: Object, default: null },
  canTrust: { type: Boolean, default: false },
  trustContent: { type: Function, required: true },
  message: { type: String, required: true },
})
const reviewModal = ref(null)
</script>
