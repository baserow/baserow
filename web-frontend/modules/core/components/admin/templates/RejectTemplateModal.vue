<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="$t(titleKey, { name: template.name })"
    :confirm-label="$t(confirmKey)"
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
        :placeholder="
          $t(
            block
              ? 'rejectTemplateModal.blockPlaceholder'
              : 'rejectTemplateModal.reasonPlaceholder'
          )
        "
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
  block: {
    type: Boolean,
    required: false,
    default: false,
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
const changesBlockReason = computed(
  () => props.block && props.template.state === 'blocked'
)

const titleKey = computed(() => {
  if (changesBlockReason.value) {
    return 'rejectTemplateModal.changeBlockReasonTitle'
  }
  if (props.block) {
    return 'rejectTemplateModal.blockTitle'
  }
  return props.template.reject_unlists
    ? 'rejectTemplateModal.unlistTitle'
    : 'rejectTemplateModal.title'
})
const description = computed(() => {
  if (changesBlockReason.value) {
    return 'rejectTemplateModal.changeBlockReasonDescription'
  }
  if (props.block) {
    return 'rejectTemplateModal.blockDescription'
  }
  if (props.template.reject_unlists) {
    return 'rejectTemplateModal.unlistDescription'
  }
  return props.template.listed
    ? 'rejectTemplateModal.editDescription'
    : 'rejectTemplateModal.description'
})

const confirmKey = computed(() => {
  if (changesBlockReason.value) {
    return 'rejectTemplateModal.changeBlockReason'
  }
  if (props.block) {
    return 'rejectTemplateModal.block'
  }
  return props.template.reject_unlists
    ? 'rejectTemplateModal.unlist'
    : 'rejectTemplateModal.reject'
})

async function show(...args) {
  reason.value = (changesBlockReason.value && props.template.reason) || ''
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
