<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="$t(copy.title, { name: template.name })"
    :confirm-label="$t(copy.button)"
    :request="makePublic"
    @done="(id, data) => emit('made-public', data)"
    @hidden="emit('hidden')"
  >
    <i18n-t
      :keypath="copy.description"
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

/**
 * Asks the author to agree that their template and their name are listed for
 * everyone on this instance, then makes the template public, or sends it to
 * review when it needs one. The button is the agreement, which the server
 * requires.
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

// A template goes to review when approval is on or an admin rejected it, see
// `needs_review`.
const copy = computed(() =>
  props.template.needs_review
    ? {
        title: 'makeTemplatePublicModal.resubmitTitle',
        description: props.template.listed
          ? 'makeTemplatePublicModal.resubmitListedDescription'
          : 'makeTemplatePublicModal.resubmitDescription',
        button: 'makeTemplatePublicModal.submitForReview',
      }
    : {
        title: 'makeTemplatePublicModal.title',
        description: 'makeTemplatePublicModal.description',
        button: 'makeTemplatePublicModal.makePublic',
      }
)

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
