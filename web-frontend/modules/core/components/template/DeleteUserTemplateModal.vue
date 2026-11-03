<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="$t('deleteUserTemplateModal.title', { name: template.name })"
    :confirm-label="$t('deleteUserTemplateModal.delete')"
    danger
    :request="deleteTemplate"
    @done="
      (id, alreadyDeleted, requestedAt) =>
        emit('deleted', id, alreadyDeleted, requestedAt)
    "
    @hidden="emit('hidden')"
  >
    <p class="user-template-modal__description margin-bottom-0">
      {{ $t('deleteUserTemplateModal.description') }}
    </p>
  </UserTemplateConfirmModal>
</template>

<script setup>
import { ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplateService from '@baserow/modules/core/services/template'
import UserTemplateConfirmModal from '@baserow/modules/core/components/template/UserTemplateConfirmModal'

/**
 * Asks the author to confirm that their template is deleted, then deletes it. The
 * deletion can't be undone.
 */
defineProps({
  // The user's template as listed in their templates.
  template: {
    type: Object,
    required: true,
  },
})

// `deleted` is emitted with the id of the deleted template, also when the modal was
// closed or opened for another template while the request ran, whether it was
// already deleted, for example in another tab, and the `performance.now()` at which
// the deletion was requested.
const emit = defineEmits(['deleted', 'hidden'])

const { $client } = useNuxtApp()

const confirmModal = ref(null)

/**
 * Resolves with whether the template was already deleted, for example in another
 * tab.
 */
async function deleteTemplate({ slug }) {
  try {
    await TemplateService($client).delete(slug)
    return false
  } catch (error) {
    if (error.response?.status === 404) {
      return true
    }
    throw error
  }
}

function show(...args) {
  confirmModal.value.show(...args)
}

function hide(...args) {
  confirmModal.value.hide(...args)
}

defineExpose({ show, hide })
</script>
