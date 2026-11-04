<template>
  <Modal
    ref="modal"
    class="templates-modal"
    :full-screen="true"
    :can-close="canClose"
  >
    <!-- Keyed by the revision, so that the preview loads its content again. -->
    <TemplateDetails
      :key="`${template.id}:${template.revision_id}`"
      :template="preview"
      :categories="template.categories || []"
      show-back
      class="templates__body"
      @back="hide()"
    >
      <template #foot>
        <div class="templates-admin-review-actions">
          <Button
            v-if="rejectLabel"
            type="secondary"
            :icon="unlists ? 'iconoir-eye-off' : 'iconoir-cancel'"
            :disabled="approving"
            full-width
            @click="emit('reject', template)"
          >
            {{ rejectLabel }}
          </Button>
          <Button
            icon="iconoir-check"
            :loading="approving"
            :disabled="approving"
            full-width
            @click="approve"
          >
            {{ $t('templatesAdmin.approve') }}
          </Button>
        </div>
      </template>
    </TemplateDetails>
  </Modal>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'
import {
  rejectUnlists,
  useTemplateReview,
} from '@baserow/modules/core/composables/useTemplateReview'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Shows the revision of a template in review or rejected, the one the admin
 * approves or rejects, with the review actions where the preview installs it.
 * Rejecting asks for a reason in the modal of the table, which `reject` is
 * emitted for.
 */
const props = defineProps({
  // The row of the template on the admin page.
  template: {
    type: Object,
    required: true,
  },
  // False while the reject modal is open on top, so that escape closes that one
  // only.
  canClose: {
    type: Boolean,
    required: false,
    default: true,
  },
})

// `reviewed` tells that the template was approved, or changed since.
const emit = defineEmits(['reject', 'reviewed'])

const { $i18n } = useNuxtApp()
const { review } = useTemplateReview()

const modal = ref(null)
const approving = ref(false)

const preview = computed(() => {
  const { author } = props.template
  return {
    ...props.template,
    author_name: author ? author.first_name || author.email : null,
  }
})

// A template in review is rejected, a listed one unlisted. A rejected one that
// isn't listed can only be approved.
const unlists = computed(() => rejectUnlists(props.template))
const rejectLabel = computed(() => {
  if (unlists.value) {
    return $i18n.t('templatesAdmin.unlist')
  }
  return props.template.state === 'in_review'
    ? $i18n.t('templatesAdmin.reject')
    : null
})

async function approve() {
  approving.value = true
  try {
    await review(props.template, 'approve')
    // The table closes the modal and refreshes the list.
    emit('reviewed')
  } catch (error) {
    notifyIf(error, 'template')
  } finally {
    approving.value = false
  }
}

function show(...args) {
  modal.value.show(...args)
}

function hide(...args) {
  modal.value.hide(...args)
}

defineExpose({ show, hide })
</script>
