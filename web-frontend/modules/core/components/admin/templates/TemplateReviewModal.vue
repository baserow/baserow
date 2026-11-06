<template>
  <Modal
    ref="modal"
    class="templates-modal"
    :full-screen="true"
    :can-close="canClose"
    :inert="!canClose"
    @hidden="restoreFocus"
  >
    <TemplateDetails
      ref="details"
      :template="preview"
      :categories="template.categories || []"
      :load-error-handler="contentFailed"
      show-back
      class="templates__body"
      @back="hide()"
    >
      <template #foot>
        <div class="templates-admin-review-actions">
          <Button
            v-if="rejectLabel"
            type="secondary"
            :icon="
              template.reject_unlists ? 'iconoir-eye-off' : 'iconoir-cancel'
            "
            :disabled="approving"
            full-width
            @click="emit('reject', template)"
          >
            {{ rejectLabel }}
          </Button>
          <Button
            icon="iconoir-check"
            :loading="approving"
            :disabled="approving || !template.can_approve"
            full-width
            @click="approve"
          >
            {{ $t('templatesAdmin.approve') }}
          </Button>
        </div>
        <p v-if="approveHint" class="templates-admin-review-hint">
          {{ $t(approveHint) }}
        </p>
      </template>
    </TemplateDetails>
  </Modal>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { useNuxtApp } from '#app'

import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'
import { useTemplateReview } from '@baserow/modules/core/composables/useTemplateReview'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { useReturnFocus } from '@baserow/modules/core/composables/useReturnFocus'

const props = defineProps({
  template: {
    type: Object,
    required: true,
  },
  // False while the reject modal is on top, so only it gets the keyboard.
  canClose: {
    type: Boolean,
    required: false,
    default: true,
  },
})

// `reviewed(id)`: the template was approved, or changed since.
const emit = defineEmits(['reject', 'reviewed'])

const { $i18n } = useNuxtApp()
const { decide, contentFailed: notifyContentChanged } = useTemplateReview()
const { remember: rememberFocus, restore: restoreFocus } = useReturnFocus()

const modal = ref(null)
const details = ref(null)
const approvingIds = reactive(new Set())

const approving = computed(() => approvingIds.has(props.template.id))

const preview = computed(() => {
  const { author } = props.template
  return {
    ...props.template,
    author_name: author ? author.first_name || author.email : null,
  }
})

const rejectLabel = computed(() => {
  if (!props.template.can_reject) {
    return null
  }
  return $i18n.t(
    props.template.reject_unlists
      ? 'templatesAdmin.unlist'
      : 'templatesAdmin.reject'
  )
})

const approveHint = computed(() => {
  if (props.template.edited_since_submitted) {
    return 'templatesAdmin.editedSinceSubmitted'
  }
  return props.template.can_approve ? null : 'templatesAdmin.noContent'
})

async function approve() {
  const template = props.template
  approvingIds.add(template.id)
  try {
    await decide(template, 'approve')
    emit('reviewed', template.id)
  } catch (error) {
    notifyIf(error, 'template')
  } finally {
    approvingIds.delete(template.id)
  }
}

function contentFailed(error) {
  const template = props.template
  if (notifyContentChanged(template, error)) {
    emit('reviewed', template.id)
  } else {
    notifyIf(error, 'templates')
  }
}

async function show(...args) {
  rememberFocus()
  modal.value.show(...args)
  await nextTick()
  details.value?.focus()
}

function hide(...args) {
  modal.value.hide(...args)
}

defineExpose({ show, hide })
</script>
