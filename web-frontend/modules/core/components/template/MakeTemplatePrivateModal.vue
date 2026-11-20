<template>
  <UserTemplateConfirmModal
    ref="confirmModal"
    :template="template"
    :title="$t('makeTemplatePrivateModal.title', { name: template.name })"
    :confirm-label="$t('makeTemplatePrivateModal.makePrivate')"
    :request="makePrivate"
    @done="(id, data) => emit('made-private', data)"
    @hidden="emit('hidden')"
  >
    <p class="user-template-modal__description margin-bottom-0">
      {{ $t(description, { name: template.name }) }}
      {{ $t(costLine) }}
    </p>
  </UserTemplateConfirmModal>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplateService from '@baserow/modules/core/services/template'
import UserTemplateConfirmModal from '@baserow/modules/core/components/template/UserTemplateConfirmModal'
import { getPublicAgainKey } from '@baserow/modules/core/utils/userTemplate'

const props = defineProps({
  template: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['made-private', 'hidden'])

const { $client, $store } = useNuxtApp()

const confirmModal = ref(null)

const description = computed(() =>
  props.template.listed
    ? 'makeTemplatePrivateModal.description'
    : 'makeTemplatePrivateModal.reviewDescription'
)

const costLine = computed(() =>
  getPublicAgainKey(
    props.template,
    $store.getters['settings/get'].user_templates_require_approval
  )
)

async function makePrivate({ slug }) {
  const { data } = await TemplateService($client).setVisibility(slug, 'private')
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
