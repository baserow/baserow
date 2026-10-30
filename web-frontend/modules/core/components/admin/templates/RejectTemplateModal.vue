<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="$t('rejectTemplateModal.title', { name: template.name })"
    :confirm-label="$t('rejectTemplateModal.reject')"
    :confirm-disabled="!trimmedReason"
    danger
    :request="() => request(trimmedReason)"
  >
    <p class="user-template-modal__description">
      {{
        $t(
          editOnly
            ? 'rejectTemplateModal.editDescription'
            : 'rejectTemplateModal.description'
        )
      }}
    </p>
    <FormGroup
      small-label
      :label="$t('rejectTemplateModal.reasonLabel')"
      required
    >
      <FormInput
        v-model="reason"
        :maxlength="MAX_REASON_LENGTH"
        :placeholder="$t('rejectTemplateModal.reasonPlaceholder')"
      ></FormInput>
    </FormGroup>
  </UserTemplateConfirmModal>
</template>

<script setup>
import { computed, ref } from 'vue'

import UserTemplateConfirmModal from '@baserow/modules/core/components/template/UserTemplateConfirmModal'

// The longest reason the server accepts.
const MAX_REASON_LENGTH = 1000

/**
 * Asks for the reason why a template is rejected, which its author sees, then
 * rejects it.
 */
defineProps({
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
  // Rejects the template with the trimmed reason.
  request: {
    type: Function,
    required: true,
  },
})

const confirmModal = ref(null)
const reason = ref('')

const trimmedReason = computed(() => reason.value.trim())

function show(...args) {
  reason.value = ''
  confirmModal.value.show(...args)
}

function hide(...args) {
  confirmModal.value.hide(...args)
}

defineExpose({ show, hide })
</script>
