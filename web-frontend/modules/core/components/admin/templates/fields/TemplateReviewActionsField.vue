<template>
  <div class="templates-admin-actions">
    <Button
      v-if="canReject"
      type="secondary"
      size="small"
      icon="iconoir-cancel"
      :disabled="pending !== null"
      @click.stop="rejectModal.show()"
    >
      {{ $t('templatesAdmin.reject') }}
    </Button>
    <Button
      v-if="canApprove"
      size="small"
      icon="iconoir-check"
      :loading="pending === 'approve'"
      :disabled="pending !== null"
      @click.stop="review('approve')"
    >
      {{ $t('templatesAdmin.approve') }}
    </Button>
    <RejectTemplateModal
      ref="rejectModal"
      :template="row"
      :edit-only="row.listed && row.state === 'in_review'"
      :loading="pending === 'reject'"
      @submit="review('reject', $event)"
    ></RejectTemplateModal>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'
import RejectTemplateModal from '@baserow/modules/core/components/admin/templates/RejectTemplateModal'
import { notifyIf } from '@baserow/modules/core/utils/error'

// The errors of a template that changed since the list was loaded, with the
// locale key of their toast: it was reviewed, edited, blocked or deleted
// meanwhile.
const CHANGED_ERRORS = {
  ERROR_TEMPLATE_ALREADY_APPROVED: 'templatesAdmin.alreadyApproved',
  ERROR_TEMPLATE_ALREADY_REJECTED: 'templatesAdmin.alreadyRejected',
  ERROR_TEMPLATE_UPDATED: 'templatesAdmin.changed',
  ERROR_TEMPLATE_NOT_REVIEWABLE: 'templatesAdmin.changed',
  ERROR_TEMPLATE_BLOCKED: 'templatesAdmin.changed',
  ERROR_TEMPLATE_DOES_NOT_EXIST: 'templatesAdmin.changed',
}

const DONE_TITLES = {
  approve: 'templatesAdmin.approved',
  reject: 'templatesAdmin.rejected',
}

const props = defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['refresh'])

const { $client, $i18n, $store } = useNuxtApp()

const rejectModal = ref(null)
// The action whose request runs.
const pending = ref(null)

// The states that the server accepts for each action. A rejected template that
// is still listed, because only its latest change was rejected, can be taken out
// of the listing.
const canReject = computed(
  () =>
    ['public', 'in_review'].includes(props.row.state) ||
    (props.row.state === 'rejected' && props.row.listed)
)
const canApprove = computed(() =>
  ['in_review', 'rejected'].includes(props.row.state)
)

/**
 * Approves or rejects the revision, state and listing that the admin sees,
 * which the server refuses when the template changed since. The list is then refreshed,
 * which moves the template to the tab of its new state.
 */
async function review(action, ...args) {
  const { id, revision_id: revisionId, name, state, listed } = props.row
  pending.value = action
  try {
    await TemplatesAdminService($client)[action](
      id,
      revisionId,
      ...args,
      state,
      listed
    )
    // The row can be gone by now, when the list was filtered or refreshed.
    $store.dispatch('toast/success', {
      title: $i18n.t(DONE_TITLES[action], { name }),
    })
    emit('refresh')
    rejectModal.value?.hide()
  } catch (error) {
    const changed = CHANGED_ERRORS[error.handler?.code]
    if (changed) {
      error.handler.notifyIf('template', {
        title: $i18n.t(`${changed}Title`, { name }),
        message: $i18n.t(`${changed}Description`),
      })
      emit('refresh')
      rejectModal.value?.hide()
    } else {
      notifyIf(error, 'template')
    }
  } finally {
    pending.value = null
  }
}
</script>
