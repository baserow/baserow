<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="
      resubmits
        ? $t('makeTemplatePublicModal.resubmitTitle', { name: template.name })
        : $t('makeTemplatePublicModal.title', { name: template.name })
    "
    :confirm-label="
      resubmits
        ? $t('makeTemplatePublicModal.submitForReviewAgain')
        : $t('makeTemplatePublicModal.makePublic')
    "
    :request="makePublic"
    @done="(id, data) => emit('made-public', data)"
    @hidden="emit('hidden')"
  >
    <i18n-t
      :keypath="description"
      tag="p"
      class="user-template-modal__description margin-bottom-0"
    >
      <template #name>{{ template.name }}</template>
      <template #author>
        <strong>{{ authorName }}</strong>
      </template>
    </i18n-t>
  </UserTemplateConfirmModal>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplateService from '@baserow/modules/core/services/template'
import UserTemplateConfirmModal from '@baserow/modules/core/components/template/UserTemplateConfirmModal'
import { makePublicResubmits } from '@baserow/modules/core/utils/userTemplate'

/**
 * Asks the author to agree to list the template and their name, then makes it
 * public or sends it to review. The button is the agreement the server needs.
 */
const props = defineProps({
  // The user's template as listed in their templates.
  template: {
    type: Object,
    required: true,
  },
})

// `made-public` is emitted with the template as listed in the user's templates,
// also when the modal was closed or opened for another template while the request
// ran.
const emit = defineEmits(['made-public', 'hidden'])

const { $client, $store } = useNuxtApp()

const confirmModal = ref(null)

// Listed already, with its edit rejected: the author resubmits the edit.
const resubmits = computed(() => makePublicResubmits(props.template))

// Whether it goes to review is the server's answer, see `make_public_needs_review`.
const description = computed(() => {
  if (!props.template.make_public_needs_review) {
    return 'makeTemplatePublicModal.description'
  }
  return props.template.listed
    ? 'makeTemplatePublicModal.resubmitListedDescription'
    : 'makeTemplatePublicModal.reviewDescription'
})

// The author of the user's own templates is the user.
const authorName = computed(() => $store.getters['auth/getName'])

async function makePublic({ slug }) {
  const { data } = await TemplateService($client).setVisibility(
    slug,
    'public',
    { publicListingConsent: true }
  )
  return data
}

function show(...args) {
  confirmModal.value.show(...args)
}

function hide(...args) {
  confirmModal.value.hide(...args)
}

defineExpose({ show, hide })
</script>
