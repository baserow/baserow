<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="$t(titleKey, { name: template.name })"
    :confirm-label="
      $t(
        template.reject_unlists
          ? 'rejectTemplateModal.unlist'
          : 'rejectTemplateModal.reject'
      )
    "
    :confirm-disabled="!trimmedReason"
    danger
    :request="(template) => request(template, trimmedReason)"
    @hidden="restoreFocus"
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
import { useReturnFocus } from '@baserow/modules/core/composables/useReturnFocus'

const MAX_REASON_LENGTH = 1000

const props = defineProps({
  template: {
    type: Object,
    required: true,
  },
  request: {
    type: Function,
    required: true,
  },
})

const { remember: rememberFocus, restore: restoreFocus } = useReturnFocus()
const confirmModal = ref(null)
const reasonInput = ref(null)
const reason = ref('')

const trimmedReason = computed(() => reason.value.trim())

const titleKey = computed(() =>
  props.template.reject_unlists
    ? 'rejectTemplateModal.unlistTitle'
    : 'rejectTemplateModal.title'
)
const description = computed(() => {
  if (props.template.reject_unlists) {
    return 'rejectTemplateModal.unlistDescription'
  }
  return props.template.listed
    ? 'rejectTemplateModal.editDescription'
    : 'rejectTemplateModal.description'
})

async function show(...args) {
  reason.value = ''
  rememberFocus()
  confirmModal.value.show(...args)
  await nextTick()
  reasonInput.value?.focus()
}

function hide(...args) {
  confirmModal.value.hide(...args)
}

defineExpose({ show, hide })
</script>
