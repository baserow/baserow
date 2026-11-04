<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="$t(titleKey, { name: template.name })"
    :confirm-label="
      $t(unlist ? 'rejectTemplateModal.unlist' : 'rejectTemplateModal.reject')
    "
    :confirm-disabled="!trimmedReason"
    danger
    :request="() => request(trimmedReason)"
  >
    <p class="user-template-modal__description">
      {{ $t(description) }}
    </p>
    <FormGroup
      small-label
      :label="$t('rejectTemplateModal.reasonLabel')"
      required
    >
      <FormInput
        ref="reasonInput"
        v-model="reason"
        :maxlength="MAX_REASON_LENGTH"
        :placeholder="$t('rejectTemplateModal.reasonPlaceholder')"
      ></FormInput>
    </FormGroup>
  </UserTemplateConfirmModal>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'

import UserTemplateConfirmModal from '@baserow/modules/core/components/template/UserTemplateConfirmModal'

// The longest reason the server accepts.
const MAX_REASON_LENGTH = 1000

/**
 * Asks for the reason why a template is rejected, which its author sees, then
 * rejects it. Rejecting a listed template takes it out of the listing, which
 * the modal calls unlisting.
 */
const props = defineProps({
  template: {
    type: Object,
    required: true,
  },
  // Whether only the latest change of a listed template is rejected, which
  // leaves the approved version listed.
  editOnly: {
    type: Boolean,
    required: false,
    default: false,
  },
  // Whether rejecting takes the template out of the listing.
  unlist: {
    type: Boolean,
    required: false,
    default: false,
  },
  // Rejects the template with the trimmed reason.
  request: {
    type: Function,
    required: true,
  },
})

const confirmModal = ref(null)
const reasonInput = ref(null)
const reason = ref('')

const trimmedReason = computed(() => reason.value.trim())

const titleKey = computed(() =>
  props.unlist ? 'rejectTemplateModal.unlistTitle' : 'rejectTemplateModal.title'
)
const description = computed(() => {
  if (props.unlist) {
    return 'rejectTemplateModal.unlistDescription'
  }
  return props.editOnly
    ? 'rejectTemplateModal.editDescription'
    : 'rejectTemplateModal.description'
})

// The reason input takes the focus, so that the keyboard doesn't stay on the
// row's buttons behind the modal.
async function show(...args) {
  reason.value = ''
  confirmModal.value.show(...args)
  await nextTick()
  reasonInput.value?.focus()
}

function hide(...args) {
  confirmModal.value.hide(...args)
}

defineExpose({ show, hide })
</script>
